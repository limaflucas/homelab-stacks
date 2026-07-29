# DevFlow Stack

Self-hosted development workflow for the agentic kanban project: **Gitea** (Git
hosting + Actions CI) and **Plane** (kanban board), deployed as the Docker Swarm
stack `devflow`.

Design and implementation plan live in
[`.docs/superpowers/`](../.docs/superpowers/) at the repository root.

---

## Architecture

Both applications reuse existing homelab infrastructure rather than adding their
own databases or object storage:

| Dependency | Provided by |
|---|---|
| PostgreSQL | `infra` stack, via `pgpool:5432` |
| Object storage | `infra` stack MinIO, bucket `plane-app` |
| Ingress + TLS | Nginx Proxy Manager over `devflow_private` |
| SSO | Authelia |

Plane additionally requires a Redis-compatible cache and RabbitMQ, neither of
which has an existing homelab equivalent; they are therefore part of this stack
(Valkey is used for the former).

---

## Prerequisites

### 1. Databases and roles

On the node holding the PostgreSQL primary (the node labelled `pg=1`):

```sql
CREATE DATABASE gitea;
CREATE USER gitea WITH PASSWORD '<gitea-db-password>';
GRANT ALL PRIVILEGES ON DATABASE gitea TO gitea;
ALTER DATABASE gitea OWNER TO gitea;

CREATE DATABASE plane;
CREATE USER plane WITH PASSWORD '<plane-db-password>';
GRANT ALL PRIVILEGES ON DATABASE plane TO plane;
ALTER DATABASE plane OWNER TO plane;
```

`ALTER DATABASE ... OWNER TO` is required, not optional: both applications run
schema migrations and need to create tables, extensions, and indexes.

### 2. MinIO bucket

Create a **private** bucket named `plane-app` and generate an access key pair
scoped to it.

### 3. Swarm secrets

```bash
printf '%s' '<gitea-db-password>' | docker secret create gitea_db_password -
printf '%s' "$(openssl rand -hex 20)" | docker secret create gitea_runner_token -
printf '%s' 'postgresql://plane:<plane-db-password>@pgpool:5432/plane' | docker secret create plane_db_url -
printf '%s' "$(openssl rand -hex 32)" | docker secret create plane_secret_key -
printf '%s' '<minio-access-key>' | docker secret create plane_minio_access_key -
printf '%s' '<minio-secret-key>' | docker secret create plane_minio_secret_key -
printf '%s' "$(openssl rand -hex 24)" | docker secret create rabbitmq_password -
```

Use `printf '%s'` rather than `echo`. A trailing newline inside a secret causes
authentication failures that present as wrong-credential errors.

| Secret | Contents |
|---|---|
| `gitea_db_password` | Password for the `gitea` Postgres role |
| `gitea_runner_token` | Shared runner registration token (40 hex chars) |
| `plane_db_url` | Full `postgresql://` URL for Plane |
| `plane_secret_key` | Django `SECRET_KEY` for Plane |
| `plane_minio_access_key` | MinIO access key for `plane-app` |
| `plane_minio_secret_key` | MinIO secret key for `plane-app` |
| `rabbitmq_password` | Password for the `plane` RabbitMQ user |

### 4. Network

`devflow_private` is declared in the `infra` stack so that Nginx Proxy Manager
can join it. Deploy `infra` before `devflow`:

```bash
docker stack deploy -c infra/compose.yaml infra
```

### 5. Host directories

```bash
sudo mkdir -p /mnt/docker-data/services/gitea/data
sudo chown -R 1000:1000 /mnt/docker-data/services/gitea
```

```bash
sudo mkdir -p /mnt/docker-data/services/gitea-runner/data
sudo cp devflow/config/gitea-runner-config.yaml \
        /mnt/docker-data/services/gitea-runner/config.yaml

sudo mkdir -p /mnt/docker-data/services/plane/{data,logs}
sudo mkdir -p /mnt/docker-data/services/valkey
sudo mkdir -p /mnt/docker-data/services/rabbitmq
```

---

## Deploy

```bash
docker stack deploy -c compose.yaml devflow
```

---

## Gitea

Git hosting and Actions CI. Backed by the `gitea` database on `pgpool`.

- **Web:** `https://gitea.homelab` (NPM → `gitea:3000`)
- **SSH:** port `2222` on the host
- **Registration is disabled.** The first account created through the setup
  wizard is the administrator; further users must be invited.

Database credentials are read from a Docker secret using Gitea's native
`__FILE` suffix (`GITEA__database__PASSWD__FILE`) — no entrypoint override is
needed.

### NPM proxy host

| Setting | Value |
|---|---|
| Domain | `gitea.homelab` |
| Forward to | `gitea` port `3000` |
| Certificate | Internal step-ca ACME |
| Websockets | **Enabled** — required for Actions log streaming |

### Verify

```bash
docker run --rm --network devflow_private curlimages/curl:latest \
  -sf http://gitea:3000/api/healthz
```

A `"status": "pass"` response also proves the `gitea` database role and
ownership are correct — the healthcheck pings Postgres.

---

## Gitea Actions runner

Executes CI workflows. Registers itself against Gitea using the shared
`gitea_runner_token` secret, so no token needs to be copied out of the admin UI
and a redeploy never requires re-registration.

Configuration lives in [`config/gitea-runner-config.yaml`](config/gitea-runner-config.yaml),
mounted read-only from `/mnt/docker-data/services/gitea-runner/config.yaml`.

Two properties of that config are load-bearing:

- **`container.network: devflow_private`** — job containers join the same
  overlay as Gitea, so `actions/checkout` can reach `http://gitea:3000` by
  service name. The default (a per-job bridge network) cannot resolve Gitea.
- **`container.docker_host: "-"`** — the Docker socket is available to the
  runner but is *not* mounted into job containers. Workflow code is
  agent-authored; a mounted socket is root on the node.

The runner is pinned to `vm-docker-bragi` via a placement constraint. It drives
that node's Docker socket to spawn sibling job containers, which are not
swarm-managed and exist only on that node — so placement cannot float.

Workflows select it with `runs-on: homelab`.

### Verify

```bash
docker service logs devflow_gitea-runner --tail 30
```

Look for a successful registration followed by `Runner registered successfully`
and polling messages. The runner then appears under
**Site Administration → Actions → Runners** with the `homelab` label.

The default job image is Node-only, so Go workflows need `actions/setup-go`.

---

## Plane

Kanban board, deployed from the all-in-one community image. No `latest` tag is
published for it — the version is pinned explicitly.

- **Web:** `https://plane.homelab` (NPM → `plane:80`)
- Backed by the `plane` database on `pgpool`, the `plane-app` MinIO bucket,
  and the `valkey` / `rabbitmq` services in this stack.

### Two constraints imposed by the image

Both are worked around by the `command:` wrapper on the `plane` service.

**1. Most environment variables cannot be set through `environment:`.**
`/app/start.sh` writes the ~20 keys it manages into `/app/plane.env`, then runs
`export $(grep -v '^#' plane.env | xargs)`. That re-export resets every other
variable to the image default, overriding anything compose passed in. Only these
are settable directly:

`DOMAIN_NAME`, `APP_PROTOCOL`, `SITE_ADDRESS`, `DATABASE_URL`, `REDIS_URL`,
`AMQP_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_S3_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, `SECRET_KEY`, `FILE_SIZE_LIMIT`,
`LIVE_SERVER_SECRET_KEY`, `API_KEY_RATE_LIMIT`.

Anything else — including `WEBHOOK_ALLOWED_HOSTS` — has to be appended to
`/app/plane.env` before `start.sh` runs. The appended line wins because `export`
takes the last occurrence of a key.

**2. There is no `_FILE` secret support.** Secrets are read from
`/run/secrets/` and exported by the wrapper before `start.sh` performs its
required-variable check.

> `start.sh` applies these values with `sed s|^key=.*|key=value|`. A password
> containing `&` will be mangled, because `&` is the whole-match reference in a
> sed replacement. Avoid `&` and `|` in the Plane database password.

### RabbitMQ credentials

`RABBITMQ_DEFAULT_PASS_FILE` and `RABBITMQ_DEFAULT_USER_FILE` are on the image's
hard-fail deprecation list — setting either aborts startup. The plain
`RABBITMQ_DEFAULT_*` variables still work, but would put the password in
plaintext in `compose.yaml`, so the entrypoint writes them from the secret into
`/etc/rabbitmq/conf.d/20-plane.conf` instead.

Two details there are easy to get wrong, and both were verified against the
image rather than assumed:

- The generated file must be **readable by the `rabbitmq` user**. Using `umask`
  to protect it also leaks the mask past `exec` into the broker, which then
  fails on its own Erlang cookie with `eacces`. Use `chown` + explicit `chmod`.
- The real entrypoint is re-invoked as `docker-entrypoint.sh rabbitmq-server`
  so that it still chowns `/var/lib/rabbitmq` and drops to the `rabbitmq` user.
  Starting the broker directly would leave it running as root.

These credentials only apply on a **first** boot against an empty data
directory. Rotating `rabbitmq_password` later requires clearing
`/mnt/docker-data/services/rabbitmq`.

### Webhook allowlist

Plane refuses to deliver webhooks to targets that resolve to private IPs. Every
agent component lives on `devflow_private`, so `WEBHOOK_ALLOWED_HOSTS` must name
them or the board → agent trigger fails **silently**. It is currently set to
`conductor`; extend it as components are added.

### NPM proxy host

| Setting | Value |
|---|---|
| Domain | `plane.homelab` |
| Forward to | `plane` port `80` |
| Certificate | Internal step-ca ACME |
| Websockets | **Enabled** — required for live board updates |

TLS terminates at NPM. `SITE_ADDRESS=:80` keeps the image's bundled Caddy on
plain HTTP so it does not attempt its own ACME.

### Verify

```bash
docker service ps devflow_plane --no-trunc
docker service logs devflow_plane --tail 100
docker run --rm --network devflow_private curlimages/curl:latest \
  -sf -o /dev/null -w '%{http_code}\n' http://plane:80/
```

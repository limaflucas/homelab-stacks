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

The runner directories must exist **on `vm-docker-adam`**, the node the runners
are pinned to — these are node-local bind mounts, not shared storage:

```bash
for s in api web mobile; do
  sudo mkdir -p /mnt/docker-data/services/gitea-runner-$s/data
  sudo cp devflow/config/gitea-runner-$s.yaml \
          /mnt/docker-data/services/gitea-runner-$s/config.yaml
done
```

```bash
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
- **SSH:** host port `2222` → container port **`22`**
- **Registration is disabled.** The first account created through the setup
  wizard is the administrator; further users must be invited.

```bash
git clone ssh://git@gitea.homelab:2222/<owner>/<repo>.git
```

SSH does **not** go through NPM — it is a published swarm port, not a proxied
one, so it is served by the routing mesh on every node's IP rather than by
whichever node happens to hold NPM.

The two ports are asymmetric on purpose, and the asymmetry is the easy thing to
get wrong:

| Setting | Value | Meaning |
|---|---|---|
| `GITEA__server__SSH_PORT` | `2222` | Port *advertised* in clone URLs |
| published port | `2222:22` | Host `2222` → the container's OpenSSH daemon |

This is the **non-rootless** `gitea/gitea:1` image, which serves Git over an
integrated OpenSSH daemon listening on container port `22`. `SSH_LISTEN_PORT`
is therefore **not** applicable — Gitea reads it only when
`START_SSH_SERVER=true`, which selects the built-in Go SSH server instead. That
is the rootless image's model, and most `2222:2222` examples online assume it.
Setting `SSH_LISTEN_PORT` here is silently inert: sshd stays on `22` and the
mapping breaks.

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

## Gitea Actions runners

One runner, `devflow_gitea-runner`, serving every build surface at capacity 5.
It registers itself against Gitea using the shared `gitea_runner_token` secret,
so no token needs to be copied out of the admin UI and a redeploy never requires
re-registration.

| Runner service | Label | Fallback image | Capacity |
|---|---|---|---|
| `devflow_gitea-runner` | `homelab` | `docker.gitea.com/runner-images:ubuntu-24.04` | 5 |

**The label's image is only a fallback.** Workflows name the image they want:

```yaml
jobs:
  lint:
    runs-on: homelab
    container:
      image: registry.homelab/shopper/ci-api:1.0.0
      credentials:
        username: ${{ secrets.REGISTRY_USERNAME }}
        password: ${{ secrets.REGISTRY_PASSWORD }}
```

act_runner honours `jobs.<id>.container.image` ahead of the label's default, so
a job that lands on the fallback simply forgot to declare one.

This is why there is one runner rather than three. The label→image mapping is
fixed at registration, so three job images once meant three runner services.
Once projects name their own images, that mapping has nothing left to do — and
keeping it would have meant a homelab redeploy every time a project bumped its
toolchain, which is exactly the coupling this arrangement removes.

Config lives in [`config/gitea-runner.yaml`](config/gitea-runner.yaml), mounted
read-only from `/mnt/docker-data/services/gitea-runner/config.yaml`, alongside a
`data/` directory holding the `.runner` registration file.

Three properties of that config are load-bearing:

- **`container.network: devflow_private`** — job containers join the same
  overlay as Gitea, so `actions/checkout` can reach `http://gitea:3000` by
  service name. The default (a per-job bridge network) cannot resolve Gitea.
- **`container.docker_host: "-"`** — the Docker socket is available to the
  runner but is *not* mounted into job containers. Workflow code is
  agent-authored; a mounted socket is root on the node. Images are built by
  Komodo, so no job here needs this relaxed.
- **`runner.labels`** — applied **at registration**. Editing it and redeploying
  re-registers the runner; confirm the change landed in **Site Administration →
  Actions → Runners** rather than assuming it did.

It is pinned to `vm-docker-adam` by an `==` placement constraint. It drives that
node's Docker socket to spawn sibling job containers, which are not swarm-managed
and exist only on that node. A `!=` constraint is not sufficient: it lets the
task float to another node, come up with no `.runner` file, and register a second
time under the same name, leaving an orphaned offline runner behind in Gitea.

`capacity: 5` replaces the previous 2 + 2 + 1, so total concurrency is unchanged.
Note the service's `memory: 2G` limit bounds the runner process only — job
containers are non-swarm siblings and are not covered by it.

### Verify

```bash
docker service logs devflow_gitea-runner 2>&1 \
  | grep -o 'runner: [^,]*, with version: [^,]*, with labels: \[[^]]*\]' | tail -1
```

Expected — a single runner:

```
runner: vm-docker-adam, with version: v2.3.0, with labels: [homelab]
```

After consolidating, the three previous registrations (`vm-docker-adam-api`,
`-web`, `-mobile`) linger as offline entries. Remove them under **Site
Administration → Actions → Runners**; they do not expire on their own.

---

## CI job images

**CI images are owned by the projects that use them, not by this repo.** Each
project keeps versioned Dockerfiles under its own `.ci/`, and Komodo builds and
publishes them to `registry.homelab/<project>/`.

This repo provides the capability — Gitea, the runner, Komodo, the registry — and
holds no application artifacts. A toolchain bump is a change in the project that
needs it, with no homelab pull request and no runner redeploy.

Design: [`.docs/superpowers/specs/2026-07-30-project-owned-ci-images-design.md`](../.docs/superpowers/specs/2026-07-30-project-owned-ci-images-design.md).

| Project | Images |
|---|---|
| `shopper` | `registry.homelab/shopper/ci-api`, `ci-web`, `ci-mobile` |

Build flow — a push touching `.ci/**` runs a thin, path-filtered workflow that
calls Komodo's API (Komodo's own webhooks filter by branch only). The workflow
needs no Docker socket; it only makes HTTP calls.

Tags are immutable. The Komodo builds disable `auto_increment_version`,
`include_latest_tag` and `include_version_tags`, so the repo declares the version
and no tag a job references is ever republished with different content. This
matters because the runner sets `force_pull: false`: a node that has cached a tag
never re-pulls it, so an overwritten tag would leave nodes silently disagreeing
about what CI runs.

> **Migration in progress.** [`ci-images/`](ci-images/) still holds the previous
> `devflow-ci-*` Dockerfiles and the images remain in the registry. They are
> removed once `shopper/.ci/` is verified end to end. Until then, workflows may
> reference either.

### Internal CA

Job images install the step-ca root so `git clone https://gitea.homelab/...` and
other internal HTTPS calls work. The certificate is **never committed**. Komodo's
`pre_build` copies the live file into the build context, and the Dockerfile
verifies it against a pinned SHA-256 fingerprint before installing it.

`komodo-periphery` runs `mode: global` and already bind-mounts the authoritative
file (`infra/compose.yaml:372`), so it is present wherever a build lands:

```
/mnt/docker-data/services/step-ca/certs/root_ca.crt
  → /usr/local/share/ca-certificates/homelab-root-ca.crt:ro
```

Reading the file rather than fetching over HTTPS is deliberate. `stepca.homelab`
has no DNS record and `infra_public` is not attachable, so a network fetch would
have needed a new DNS entry plus an NPM proxy exposing the CA's management API —
real added surface to retrieve a certificate that is already public. Reading the
file also means a build cannot fail because step-ca happens to be down.

The fingerprint is what makes this safe to automate; get it with:

```bash
docker exec -it $(docker ps -q -f name=infra_step-ca) \
  step certificate fingerprint /home/step/certs/root_ca.crt
```

It is a hash of a public certificate, so committing it is intended — unlike the
certificate itself, it is short, self-verifying, and reviewable in a diff.

Node-based images must also set `NODE_EXTRA_CA_CERTS`; Node does not read the
system trust pool.

### Registry credentials

`registry.homelab` requires auth for pulls as well as pushes. Workflows supply it
per job:

```yaml
container:
  image: registry.homelab/shopper/ci-api:1.0.0
  credentials:
    username: ${{ secrets.REGISTRY_USERNAME }}
    password: ${{ secrets.REGISTRY_PASSWORD }}
```

Set `REGISTRY_USERNAME` / `REGISTRY_PASSWORD` as **organisation-level** Gitea
secrets so every repo in the org inherits them.

**The nodes need no registry login.** This previously depended on a standing
`docker login registry.homelab` on `vm-docker-adam` — undocumented per-node state
that a rebuilt node loses silently, surfacing as an image pull failure with no
obvious cause. Declared credentials replace it. The runner's own fallback image
is public.

> Do **not** deploy this stack with `--with-registry-auth`. Doing so ships the
> deploying workstation's credentials to the nodes and overrides the anonymous
> Docker Hub access that works there, which takes `gitea`, `valkey` and `plane`
> down with `No such image` until they are redeployed without the flag.

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

---

## Board states

[`scripts/bootstrap-plane-board.py`](scripts/bootstrap-plane-board.py)
reconciles a project's states with the workflow topology. It is idempotent:
it creates what is missing, corrects the group and colour of what already
exists, and with `--prune` removes Plane's defaults.

Run it from inside the overlay, where Plane is plain HTTP and no certificate
trust is involved:

```bash
export PLANE_API_KEY=plane_api_...    # Plane -> Profile settings -> Personal access tokens

run() { docker run --rm -i --network devflow_private \
          -e PLANE_API_KEY -e PLANE_BASE_URL=http://plane:80 \
          python:3-alpine python - "$@" \
          < devflow/scripts/bootstrap-plane-board.py; }

run --workspace <slug> --list-projects
run --workspace <slug> --project <uuid> --dry-run
run --workspace <slug> --project <uuid> --prune
```

The topology, and who owns each state:

| # | State | Group | Owner |
|---|---|---|---|
| 1 | Inbox | backlog | Operator |
| 2 | Refining | unstarted | Agent |
| 3 | ❓ Needs Answer | unstarted | **Operator — gate 1** |
| 4 | Ready | unstarted | Agent |
| 5 | Planning | started | Agent |
| 6 | 📋 Plan Review | started | **Operator — gate 2** |
| 7 | In Progress | started | Agent |
| 8 | 🔍 PR Review | started | **Operator — gate 3** |
| 9 | 🚀 Deploy Approval | started | **Operator — gate 4** |
| 10 | Done | completed | — |
| 11 | ⚠️ Blocked | cancelled | Operator |

Every state is owned unambiguously by one party, and approval is expressed by
**moving the card** rather than by writing a comment for something to parse.
The four gates share one colour so that "is the board waiting on me?" is
answerable at a glance.

Plane will refuse to delete a project's default state, and any state that still
contains work items — `--prune` reports those as `SKIPPED` rather than failing.
If `Backlog` survives pruning, set `Inbox` as the project default in the UI and
re-run.

---

## LLM budget

Agent runners never hold a raw Anthropic key. They authenticate to LiteLLM with
a virtual key that carries its own spend cap, stored as the swarm secret
`devflow_agent_llm_key`.

| Property | Value |
|---|---|
| Key alias | `devflow-agent` |
| Cap | `max_budget: 50` over `budget_duration: "30d"` |
| Rate limit | `rpm_limit: 60` |
| Model allowlist | `claude-sonnet-5`, `claude-haiku-4-5`, `qwen2.5-coder:7b` |
| Swarm secret | `devflow_agent_llm_key` |

Runners reach it over the Anthropic passthrough proven in
[`llms/.docs/claude-code-passthrough-spike.md`](../llms/.docs/claude-code-passthrough-spike.md):

```bash
ANTHROPIC_BASE_URL=http://litellm:4000/anthropic
ANTHROPIC_AUTH_TOKEN=<contents of devflow_agent_llm_key>
```

The allowlist is enforced, not advisory. Requesting a model outside it returns
`403` with `"type": "key_model_access_denied"`, so a runner cannot quietly
escape the cap by naming a different model.

### Budget-exceeded response shape

The Conductor keys its `⚠️ Blocked` transition off this exact response. Verified
by issuing calls against a throwaway key with `max_budget: 0.0001`: the first
call succeeded, and **every** subsequent call failed closed with HTTP `429`:

```json
{
  "error": {
    "message": "Budget has been exceeded! Key=budget-test (sk-...k5qg) Current cost: 0.000674, Max budget: 0.0001",
    "type": "budget_exceeded",
    "param": null,
    "code": "429"
  }
}
```

Two details matter for whatever parses this:

- **The `/anthropic` passthrough returns this same LiteLLM envelope**, *not*
  Anthropic's native `{"type":"error","error":{"type":"..."}}` error shape. Match
  on `error.type == "budget_exceeded"` or the `429` status — not on Anthropic's
  error vocabulary.
- **Match the type, not the message.** The message embeds the running cost and a
  key fragment, so it differs on every occurrence.

### Spend accounting

`proxy_batch_write_at: 60` in the LiteLLM config means spend is flushed in
batches. A just-issued call may not be reflected in `key/info` immediately, and
the cap is therefore enforced slightly late — a key can overshoot its budget by
roughly one call. At a $50 cap this is immaterial, but it is why the exhaustion
test above needed a spread of attempts rather than three rapid ones.

Check current spend:

```bash
CID=$(docker ps -qf name=llms_litellm)   # runs on vm-docker-zeus
docker exec -i $CID sh -c 'read K; curl -s "http://localhost:4000/key/info?key=$K" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY"' </path/to/key \
  | jq -c '.info | {key_alias, max_budget, spend, budget_reset_at}'
```

> `budget_duration: "30d"` does **not** mean "30 days from issue". LiteLLM
> reported `budget_reset_at: 2026-08-01` for a key created on 2026-07-30 — it
> aligns the window to the upcoming month boundary, so the first window can be
> far shorter than 30 days. The cap itself is enforced normally; only the reset
> date is surprising.

### Rotating the key

The cap lives on the key, so rotation is generate → replace secret → redeploy:

```bash
CID=$(docker ps -qf name=llms_litellm)
docker exec $CID sh -c 'curl -s -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
  -d "{\"key_alias\":\"devflow-agent\",\"models\":[\"claude-sonnet-5\",\"claude-haiku-4-5\",\"qwen2.5-coder:7b\"],
       \"max_budget\":50,\"budget_duration\":\"30d\",\"rpm_limit\":60}"' | jq -r '.key'
```

Swarm secrets are immutable, so the old one must be removed and recreated, then
every service consuming it redeployed. Use `printf '%s'` — a trailing newline in
the key presents as an authentication failure, not as a formatting problem.

Delete the superseded key from LiteLLM afterwards so its remaining budget cannot
be spent:

```bash
docker exec $CID sh -c 'curl -s -X POST http://localhost:4000/key/delete \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
  -d "{\"keys\":[\"sk-OLD_KEY\"]}"'
```

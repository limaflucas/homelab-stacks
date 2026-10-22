# devflow

Gitea (Git and Actions CI) and Plane (kanban board) for the agentic kanban workflow. Design notes are in [`.docs/superpowers/`](../.docs/superpowers/).

| Service | Purpose |
| :--- | :--- |
| `gitea` | `https://gitea.homelab`, SSH on port 2222 |
| `gitea-runner` | Actions runner, label `homelab`, capacity 5 |
| `plane` | `https://plane.homelab` |
| `valkey`, `rabbitmq` | Plane's cache and job broker |

The `gitea` and `plane` databases are on PostgreSQL (192.168.5.30). Plane stores files in the MinIO bucket `plane-app`.

## Setup

On the PostgreSQL primary. Both apps run migrations, so they must own their databases.

```sql
CREATE DATABASE gitea;
CREATE USER gitea WITH PASSWORD '<password>';
ALTER DATABASE gitea OWNER TO gitea;
CREATE DATABASE plane;
CREATE USER plane WITH PASSWORD '<password>';
ALTER DATABASE plane OWNER TO plane;
```

Create a private MinIO bucket `plane-app` with its own access key. Then create the secrets. Use `printf '%s'`, because a trailing newline breaks authentication:

```bash
printf '%s' '<gitea db password>' | docker secret create gitea_db_password -
printf '%s' "$(openssl rand -hex 20)" | docker secret create gitea_runner_token -
printf '%s' 'postgresql://plane:<password>@192.168.5.30:5432/plane' | docker secret create plane_db_url_v2 -
printf '%s' "$(openssl rand -hex 32)" | docker secret create plane_secret_key -
printf '%s' '<minio access key>' | docker secret create plane_minio_access_key -
printf '%s' '<minio secret key>' | docker secret create plane_minio_secret_key -
printf '%s' "$(openssl rand -hex 24)" | docker secret create rabbitmq_password -
```

Host directories under `/mnt/docker-data/services/`:
*   `gitea/data`, owned by `1000:1000`
*   `gitea-runner/data` and `gitea-runner/config.yaml` (a copy of [`config/gitea-runner.yaml`](config/gitea-runner.yaml))
*   `plane/{data,logs}`
*   `valkey`
*   `rabbitmq`

Deploy `infra` first, since it declares `devflow_private`. Then:

```bash
docker stack deploy -c compose.yaml devflow
```

Don't add `--with-registry-auth`: it overrides the nodes' anonymous Docker Hub access, and `gitea`, `valkey` and `plane` then fail with `No such image`.

## Gitea

*   Registration is closed. The first account, created in the setup wizard, is the admin.
*   **SSH:** `git clone ssh://git@gitea.homelab:2222/<owner>/<repo>.git`.
    *   Port 2222 on every node maps to the container's OpenSSH on port 22 (image `gitea/gitea:1`, not rootless).
    *   `SSH_PORT=2222` only sets the port shown in clone URLs. Don't set `SSH_LISTEN_PORT`: it only applies to Gitea's built-in SSH server.
*   **Health:** `docker run --rm --network devflow_private curlimages/curl -sf http://gitea:3000/api/healthz`.

## Actions runner

*   **Registration:** the runner registers itself with the `gitea_runner_token` secret. Its `.runner` file is on GlusterFS, so it can run on any node without registering again.
*   **Jobs:** they run as sibling containers on the runner's node, outside the service's memory limit.
*   **Images:** each workflow names its own. The label's `runner-images:ubuntu-24.04` is only a fallback.

```yaml
runs-on: homelab
container:
  image: registry.homelab/shopper/ci-api:1.0.0
  credentials:
    username: ${{ secrets.REGISTRY_USERNAME }}
    password: ${{ secrets.REGISTRY_PASSWORD }}
```

`REGISTRY_USERNAME` and `REGISTRY_PASSWORD` are organisation-level Gitea secrets, so the nodes need no registry login.

Settings in `config/gitea-runner.yaml`:
*   `container.network: devflow_private`: jobs can reach `http://gitea:3000`.
*   `container.docker_host: "-"`: jobs get no Docker socket, which would mean root on the node.
*   `force_pull: false`: cached tags are reused, which is safe because CI image tags never change.
*   `runner.labels`: these apply at registration. After changing them, check **Site Administration → Actions → Runners**.

## CI images

*   **Ownership:** each project owns its CI images under its own `.ci/`. Komodo builds them into `registry.homelab/<project>/` with fixed version tags. Current: `shopper` (`ci-api`, `ci-web`, `ci-mobile`).
*   **Trust:** images trust the homelab root CA. Komodo's `pre_build` copies it from the periphery container (`/usr/local/share/ca-certificates/homelab-root-ca.crt`), and the image checks its SHA-256 fingerprint (see [infra](../infra/README.md#certificates-step-ca)).
*   **Node images:** they also need `NODE_EXTRA_CA_CERTS`.
*   **Legacy:** [`ci-images/`](ci-images/) holds the older `devflow-ci-*` images, to be removed once `shopper/.ci/` is verified.

## Plane

The image is `makeplane/plane-aio-community:stable`. The `command:` wrapper works around it:
*   **Environment:** `start.sh` re-exports `/app/plane.env`, overriding most `environment:` values.
    *   Only these pass through: `DOMAIN_NAME`, `APP_PROTOCOL`, `SITE_ADDRESS`, `DATABASE_URL`, `REDIS_URL`, `AMQP_URL`, `AWS_*`, `SECRET_KEY`, `FILE_SIZE_LIMIT`, `LIVE_SERVER_SECRET_KEY` and `API_KEY_RATE_LIMIT`.
    *   Anything else is appended to `/app/plane.env`, e.g. `WEBHOOK_ALLOWED_HOSTS=conductor`. Plane only sends webhooks to private hosts listed there.
*   **Secrets:** the image has no `_FILE` support, so the wrapper exports them from `/run/secrets/`.
*   **Directories:** the wrapper recreates `/app/logs/{access,error}` and `/app/data`, which the bind mounts hide.
*   **Database password:** avoid `&` and `|`, because `start.sh` applies it with `sed`.
*   **TLS:** `SITE_ADDRESS=:80` keeps the bundled Caddy on plain HTTP; Traefik terminates TLS.

**RabbitMQ:**
*   Its `_FILE` variables abort startup. Instead, the entrypoint writes the credentials to `/etc/rabbitmq/conf.d/20-plane.conf`, owned by `rabbitmq` and set with `chmod` rather than `umask`. Then it runs `docker-entrypoint.sh rabbitmq-server`.
*   The credentials only apply on first boot. To rotate `rabbitmq_password`, clear `/mnt/docker-data/services/rabbitmq`.

## Board states

[`scripts/bootstrap-plane-board.py`](scripts/bootstrap-plane-board.py) makes a project's states match the table below. It's safe to re-run, and `--prune` removes Plane's defaults.

```bash
export PLANE_API_KEY=plane_api_...
run() { docker run --rm -i --network devflow_private -e PLANE_API_KEY -e PLANE_BASE_URL=http://plane:80 \
          python:3-alpine python - "$@" < devflow/scripts/bootstrap-plane-board.py; }
run --workspace <slug> --list-projects
run --workspace <slug> --project <uuid> --dry-run
run --workspace <slug> --project <uuid> --prune
```

| # | State | Group | Owner |
|---|---|---|---|
| 1 | Inbox | backlog | Operator |
| 2 | Refining | unstarted | Agent |
| 3 | ❓ Needs Answer | unstarted | **Operator, gate 1** |
| 4 | Ready | unstarted | Agent |
| 5 | Planning | started | Agent |
| 6 | 📋 Plan Review | started | **Operator, gate 2** |
| 7 | In Progress | started | Agent |
| 8 | 🔍 PR Review | started | **Operator, gate 3** |
| 9 | 🚀 Deploy Approval | started | **Operator, gate 4** |
| 10 | Done | completed | none |
| 11 | ⚠️ Blocked | cancelled | Operator |

Approval means moving the card. Plane won't delete the default state or states that still hold work items; if `Backlog` survives `--prune`, make `Inbox` the default and run it again.

## LLM budget

Agent runners use the LiteLLM virtual key `devflow-agent`, stored in the swarm secret `devflow_agent_llm_key`:
*   **Budget:** $50 per 30 days. The window aligns to month boundaries, so the first one can be short.
*   **Rate:** 60 requests per minute.
*   **Models:** `claude-sonnet-5`, `claude-haiku-4-5` and `qwen2.5-coder:7b`. Any other model returns `403`.

```bash
ANTHROPIC_BASE_URL=http://litellm:4000/anthropic
ANTHROPIC_AUTH_TOKEN=<contents of devflow_agent_llm_key>
```

**When the budget runs out:**
*   Every call returns HTTP `429` with `error.type == "budget_exceeded"`, in LiteLLM's format even on `/anthropic`. Match on that type, not on the message.
*   Spend is written in batches every 60 seconds, so a key can overshoot by about one call.

**To rotate the key:**
1.  Create a new key with the same limits:

    ```bash
    CID=$(docker ps -qf name=llms_litellm)
    docker exec $CID sh -c 'curl -s -X POST http://localhost:4000/key/generate \
      -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
      -d "{\"key_alias\":\"devflow-agent\",\"models\":[\"claude-sonnet-5\",\"claude-haiku-4-5\",\"qwen2.5-coder:7b\"],
           \"max_budget\":50,\"budget_duration\":\"30d\",\"rpm_limit\":60}"' | jq -r '.key'
    ```

2.  Recreate the secret with `printf '%s'` and redeploy the services that use it.
3.  Delete the old key:

    ```bash
    docker exec $CID sh -c 'curl -s -X POST http://localhost:4000/key/delete \
      -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
      -d "{\"keys\":[\"sk-OLD_KEY\"]}"'
    ```

# devflow

Gitea (Git hosting), Plane (kanban board) and Unleash (feature flags).

| Service | Purpose |
| :--- | :--- |
| `gitea` | `https://gitea.homelab`, SSH on port 2222 |
| `plane` | `https://plane.homelab` |
| `valkey`, `rabbitmq` | Plane's cache and job broker |
| `unleash` | `https://unleash.homelab`, feature flags for cahier and rhuthmos |

The `gitea`, `plane` and `unleash` databases are on PostgreSQL (192.168.5.30). Plane stores files in the MinIO bucket `plane-app`.

## Setup

On the PostgreSQL primary. The apps run migrations, so they must own their databases.

```sql
CREATE DATABASE gitea;
CREATE USER gitea WITH PASSWORD '<password>';
ALTER DATABASE gitea OWNER TO gitea;
CREATE DATABASE plane;
CREATE USER plane WITH PASSWORD '<password>';
ALTER DATABASE plane OWNER TO plane;
CREATE DATABASE unleash;
CREATE USER unleash WITH PASSWORD '<password>';
ALTER DATABASE unleash OWNER TO unleash;
```

Create a private MinIO bucket `plane-app` with its own access key. Then create the secrets. Use `printf '%s'`, because a trailing newline breaks authentication:

```bash
printf '%s' '<gitea db password>' | docker secret create gitea_db_password -
printf '%s' 'postgresql://plane:<password>@192.168.5.30:5432/plane' | docker secret create plane_db_url_v2 -
printf '%s' "$(openssl rand -hex 32)" | docker secret create plane_secret_key -
printf '%s' '<minio access key>' | docker secret create plane_minio_access_key -
printf '%s' '<minio secret key>' | docker secret create plane_minio_secret_key -
printf '%s' "$(openssl rand -hex 24)" | docker secret create rabbitmq_password -
printf "DATABASE_URL='%s'\nUNLEASH_SECRET='%s'\nUNLEASH_DEFAULT_ADMIN_USERNAME='%s'\nUNLEASH_DEFAULT_ADMIN_PASSWORD='%s'\nINIT_ADMIN_API_TOKENS='%s'\n" \
  'postgres://unleash:<password>@192.168.5.30:5432/unleash' "$(openssl rand -hex 32)" admin '<admin password>' "*:*.$(openssl rand -hex 32)" \
  | docker secret create unleash_env_v1 -
```

Host directories under `/mnt/docker-data/services/`:
*   `gitea/data`, owned by `1000:1000`
*   `plane/{data,logs}`
*   `valkey`
*   `rabbitmq`

Deploy `infra` first, since it declares `devflow_private`. Then:

```bash
docker stack deploy -c compose.yaml devflow
```

Don't add `--with-registry-auth`: it overrides the nodes' anonymous Docker Hub access, and `gitea`, `valkey` and `plane` then fail with `No such image`.

## Gitea

*   The setup wizard opens on the first visit. The account created there is the admin, and its optional settings control registration.
*   **SSH:** `git clone ssh://git@gitea.homelab:2222/<owner>/<repo>.git`.
    *   Port 2222 on every node maps to the container's OpenSSH on port 22 (image `gitea/gitea:1`, not rootless).
    *   `SSH_PORT=2222` only sets the port shown in clone URLs. Don't set `SSH_LISTEN_PORT`: it only applies to Gitea's built-in SSH server.
*   **Health:** `docker run --rm --network devflow_private curlimages/curl -sf http://gitea:3000/api/healthz`.
*   **Webhooks:** Gitea only calls hosts listed in `[security] ALLOWED_HOST_LIST`, set to `komodo.homelab`. The mounted homelab root CA lets it verify Komodo's certificate, because Go reads every file in `/etc/ssl/certs`.

## Plane

The image is `makeplane/plane-aio-community:stable`. The `command:` wrapper works around it:
*   **Environment:** `start.sh` re-exports `/app/plane.env`, overriding most `environment:` values.
    *   Only these pass through: `DOMAIN_NAME`, `APP_PROTOCOL`, `SITE_ADDRESS`, `DATABASE_URL`, `REDIS_URL`, `AMQP_URL`, `AWS_*`, `SECRET_KEY`, `FILE_SIZE_LIMIT`, `LIVE_SERVER_SECRET_KEY` and `API_KEY_RATE_LIMIT`.
    *   To set anything else, append it to `/app/plane.env` in the wrapper before `exec /app/start.sh`.
*   **Secrets:** the image has no `_FILE` support, so the wrapper exports them from `/run/secrets/`.
*   **Directories:** the wrapper recreates `/app/logs/{access,error}` and `/app/data`, which the bind mounts hide.
*   **Database password:** avoid `&` and `|`, because `start.sh` applies it with `sed`.
*   **TLS:** `SITE_ADDRESS=:80` keeps the bundled Caddy on plain HTTP; Traefik terminates TLS.
*   **MinIO TLS:** boto3 ignores the system trust store, so `AWS_CA_BUNDLE` points it at the mounted homelab root CA. Without it, server-side calls to `api.minio.homelab` fail certificate verification.

**RabbitMQ:**
*   Its `_FILE` variables abort startup. Instead, the entrypoint writes the credentials to `/etc/rabbitmq/conf.d/20-plane.conf`, owned by `rabbitmq` and set with `chmod` rather than `umask`. Then it runs `docker-entrypoint.sh rabbitmq-server`.
*   The credentials only apply on first boot. To rotate `rabbitmq_password`, clear `/mnt/docker-data/services/rabbitmq`.

## Unleash

Feature flags for the apps that deploy from Gitea. The image is `unleashorg/unleash-server:8.2.1`.
*   **Secret:** `unleash_env_v1` is an env file. The `entrypoint:` wrapper sources it, because the image has no `_FILE` support.
*   **One project:** the open-source edition has only the `default` project and the `development` and `production` environments, so every app shares one list of flags. Name them after the app: `cahier-<name>`, `rhuthmos-<name>`.
*   **Clients:** a stack joins the external `unleash` network, which this stack declares, and calls `http://devflow_unleash:4242/api`. Server SDKs use a backend token; browsers go through their app's own server or proxy with a frontend token, never a token in the bundle.
*   **Tokens:** each app gets its own, from the admin API (`POST /api/admin/api-tokens`) or the UI. `INIT_*_API_TOKENS` only apply to an empty database.
*   **Health:** `docker run --rm --network unleash curlimages/curl -sf http://devflow_unleash:4242/health`, or `https://unleash.homelab/health`.
*   **Restarts:** `condition: any`, unlike the rest of this stack. Every app's flags read as off while Unleash is down, so it keeps retrying until Postgres is back instead of giving up after five attempts.
*   **Order:** deploy devflow before any app stack that uses Unleash. It creates the `unleash` network, and an app stack deploy aborts without it. `docker stack rm devflow` cannot remove that network while an app is still attached; the next devflow deploy reuses it.

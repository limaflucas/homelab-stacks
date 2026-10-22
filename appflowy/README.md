# appflowy

AppFlowy Cloud:
*   `appflowy-cloud`: the backend.
*   `gotrue`: authentication.
*   `appflowy-redis`: cache.
*   `appflowy-web` and `appflowy-admin`: the web and admin front ends.

Data is in the PostgreSQL database `appflowy` (192.168.5.30) and files are in MinIO (`minio_net`). `appflowy-cloud` and `appflowy-admin` mount the homelab root CA from `/mnt/docker-data/services/homelab-ca/root_ca.crt`.

## Routes

| URL | Service |
| :--- | :--- |
| `https://cloud.appflowy.homelab` | `appflowy-cloud:8000` |
| `https://cloud.appflowy.homelab/gotrue/*` | `gotrue:9999` |
| `https://gotrue.appflowy.homelab` | `gotrue:9999` |
| `https://web.appflowy.homelab` | `appflowy-web:3000` |
| `https://admin.appflowy.homelab/console` | `appflowy-admin:3000` |

The `/gotrue/` route chains three middlewares, in this order:
1.  `appflowy-gotrue-strip` removes the `/gotrue` prefix.
2.  `appflowy-gotrue-cors` allows the `web`, `cloud` and `admin` origins and sets `Host: gotrue.appflowy.homelab`.
3.  `appflowy-gotrue-hide-cors` removes gotrue's own CORS headers, so other origins get none.

Each hostname needs a pihole CNAME to `docker.homelab`.

## Database

GoTrue and AppFlowy need separate roles: GoTrue's tables live in `auth`, AppFlowy's in `public`. The app roles can't create extensions, so `postgres` creates them first. Run on the primary (CT 110):

```sql
CREATE ROLE gotrue WITH LOGIN PASSWORD '<password>';
GRANT ALL PRIVILEGES ON DATABASE appflowy TO gotrue;
GRANT ALL ON SCHEMA public TO gotrue;
ALTER ROLE gotrue IN DATABASE appflowy SET search_path TO auth, public;
ALTER ROLE appflowy IN DATABASE appflowy SET search_path TO "$user", public;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE SCHEMA IF NOT EXISTS auth;
ALTER SCHEMA auth OWNER TO gotrue;
GRANT ALL PRIVILEGES ON DATABASE appflowy TO appflowy;
GRANT ALL ON SCHEMA public TO appflowy;
GRANT USAGE ON SCHEMA auth TO appflowy;
GRANT SELECT, REFERENCES ON ALL TABLES IN SCHEMA auth TO appflowy;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT SELECT, REFERENCES ON TABLES TO appflowy;
```

## Environment

Set these in a `.env` next to `compose.yaml` (not committed):

| Variable | Value |
| :--- | :--- |
| `GOTRUE_ADMIN_EMAIL`, `GOTRUE_ADMIN_PASSWORD` | GoTrue admin |
| `GOTRUE_JWT_SECRET` | Random base64 |
| `GOTRUE_JWT_EXP` | `604800` (7 days) |
| `GOTRUE_DISABLE_SIGNUP`, `GOTRUE_MAILER_AUTOCONFIRM` | `true` or `false` |
| `GOTRUE_DATABASE_URL` | `postgres://gotrue:<password>@192.168.5.30:5432/appflowy` |
| `APPFLOWY_DATABASE_URL` | `postgres://appflowy:<password>@192.168.5.30:5432/appflowy` |
| `APPFLOWY_S3_ACCESS_KEY`, `APPFLOWY_S3_SECRET_KEY` | MinIO credentials |

## Deploy and check

```bash
docker stack deploy -c compose.yaml appflowy
curl -I https://cloud.appflowy.homelab/api/health
curl -I https://cloud.appflowy.homelab/gotrue/settings
```

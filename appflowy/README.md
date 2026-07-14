# AppFlowy Stack

This directory contains the configurations for the **AppFlowy** stack of the homelab, deployed as a single Docker Swarm stack named `appflowy`. 

It hosts the AppFlowy Cloud backend services, including real-time collaboration endpoints, user authentication (GoTrue), database caching (Redis), and frontend admin and web interfaces.

---

## Services Overview

### 1. Core Services
*   **AppFlowy Cloud** (`appflowy-cloud`): The main AppFlowy Cloud backend (Rust/Actix-web) managing workspaces, real-time collaboration, document sync, and search integrations. It mounts the `step-ca` root certificate to trust local HTTPS services and connects to MinIO for file storage.
*   **GoTrue Auth** (`gotrue`): The Netlify GoTrue identity API handling user registrations, email/password logins, and token generation. It connects to the PostgreSQL database to persist credentials in the `auth` schema.
*   **AppFlowy Redis** (`appflowy-redis`): A lightweight Redis 8 cache backend used by AppFlowy Cloud for real-time pub/sub synchronization and task queues.

### 2. Frontend Interfaces
*   **AppFlowy Web** (`appflowy-web`): The web-based client application (compiled Flutter/JS running on Nginx) allowing users to access their workspaces from any web browser.
*   **AppFlowy Admin Console** (`appflowy-admin`): The administrative frontend used to monitor seats, manage workspaces, and view system analytics.

---

## Network Architecture

The stack connects to three external overlay networks defined in the parent infrastructure:
1.  `appflowy_private` (Swarm: `appflowy_private`): Isolated network connecting all AppFlowy services to each other and allowing the Nginx Proxy Manager to route external traffic to the frontends and APIs.
2.  `pgpool_net` (Swarm: `pgpool_net`): Direct database network allowing `gotrue` and `appflowy-cloud` to communicate with the highly available PostgreSQL Pgpool-II router.
3.  `minio_net` (Swarm: `minio_net`): Direct storage network allowing `appflowy-cloud` to communicate securely with the MinIO S3 object storage backend.

---

## Prerequisites & Setup

Ensure the following prerequisites are met before deploying the stack:

### 1. Ingress Proxy Configuration
You must configure Nginx Proxy Manager (NPM) to route traffic to the following subdomains:
*   `https://cloud.appflowy.homelab` -> Proxy to `http://appflowy-cloud:8000` (enable WebSocket support).
*   `https://gotrue.appflowy.homelab` -> Proxy to `http://gotrue:9999`.
*   `https://web.appflowy.homelab` -> Proxy to `http://appflowy-web:80` (or `appflowy-admin:80` depending on path, typically `appflowy-web` runs on the main web address).
*   **Crucial Subpath Route:** Under the `cloud.appflowy.homelab` proxy host, you must define a custom location `/gotrue/` pointing to `http://gotrue:9999/` with the Host header overridden to `gotrue.appflowy.homelab` and the path prefix stripped.

### 2. Host Directories
Ensure the following persistence and certificate paths are mounted on your Swarm nodes:
*   **Step-CA Cert:** `/mnt/docker-data/services/step-ca/certs/root_ca.crt` (mounted as read-only to allow containers to build trust with local SSL domains).

---

### 3. Database Search Path & Roles (For GoTrue and AppFlowy Cloud)
Because PgBouncer operates in **transaction pooling** mode, session-level startup parameters like `search_path` are discarded to allow safe connection multiplexing. In addition, GoTrue uses Go's `pgx` library which relies on prepared statements, requiring the `statement_cache_mode=describe` connection option to prevent collisions in transaction mode.

To prevent table name collisions between GoTrue (which creates tables in the `auth` schema) and AppFlowy Cloud (which creates tables in the `public` schema), you must use **separate database users** and configure their search paths accordingly:

```sql
-- 1. Create the dedicated gotrue role (use the same password as appflowy for convenience)
CREATE ROLE gotrue WITH LOGIN PASSWORD '<your_password>';
GRANT ALL PRIVILEGES ON DATABASE appflowy TO gotrue;
GRANT ALL ON SCHEMA public TO gotrue;

-- 2. Configure search paths
ALTER ROLE gotrue IN DATABASE appflowy SET search_path TO auth, public;
ALTER ROLE appflowy IN DATABASE appflowy SET search_path TO "$user", public;
```

---

### 4. Environment Variables
The stack uses environment variables to configure database connections, S3 storage keys, and authentication parameters. These are usually injected via Komodo Core:

| Environment Variable | Description | Recommended Value |
| --- | --- | --- |
| `GOTRUE_ADMIN_EMAIL` | Admin login email for GoTrue | `admin@homelab.com` |
| `GOTRUE_ADMIN_PASSWORD` | Secure admin login password | `<your_secure_password>` |
| `GOTRUE_JWT_SECRET` | Secret key used to sign JWTs | `<random_base64_string>` |
| `GOTRUE_JWT_EXP` | Expiration time of JWTs in seconds | `604800` (7 days) |
| `GOTRUE_DATABASE_URL` | GoTrue DB connection string (targeting auth schema) | `postgres://gotrue:<password>@pgbouncer:6432/appflowy?statement_cache_mode=describe` |
| `APPFLOWY_DATABASE_URL` | AppFlowy Cloud DB connection string | `postgres://appflowy:<password>@pgbouncer:6432/appflowy` |
| `APPFLOWY_S3_ACCESS_KEY` | MinIO Access Key (root user) | `<minio_access_key>` |
| `APPFLOWY_S3_SECRET_KEY` | MinIO Secret Key (root password) | `<minio_secret_key>` |

---

## Deployment

Deploy the AppFlowy stack using Docker Swarm:

```bash
docker stack deploy -c compose.yaml appflowy
```

---

## Verification & Post-Deployment

### 1. Service Health
Verify that all services are running and healthy:
```bash
docker stack ps appflowy
```

### 2. Verify API Health
Check the main AppFlowy Cloud health endpoint:
```bash
curl -I https://cloud.appflowy.homelab/api/health
```

### 3. Verify Auth Settings API
Check the GoTrue settings subpath configuration:
```bash
curl -I https://cloud.appflowy.homelab/gotrue/settings
```

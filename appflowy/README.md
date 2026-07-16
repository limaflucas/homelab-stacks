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
*   **Crucial Subpath Route:** Under the `cloud.appflowy.homelab` proxy host, you must define a custom location `/gotrue/` pointing to `http://gotrue:9999/` (with Host header overridden to `gotrue.appflowy.homelab` and the path prefix stripped).
    
    Add the following custom Nginx configuration block to this location (or in the advanced configuration section) to properly handle CORS preflight requests and avoid duplicate headers:

    ```nginx
    location /gotrue/ {
        set $cors_origin "";
        if ($http_origin ~* ^https://(web|cloud|admin)\.appflowy\.homelab$) {
            set $cors_origin $http_origin;
        }

        # Preflight — short-circuit before it ever reaches gotrue
        if ($request_method = OPTIONS) {
            add_header 'Access-Control-Allow-Origin' $cors_origin always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-Client-Info, Apikey' always;
            add_header 'Access-Control-Allow-Credentials' 'true' always;
            add_header 'Access-Control-Max-Age' 86400 always;
            return 204;
        }

        # In case gotrue emits its own (possibly wrong) CORS headers, don't let them double up
        proxy_hide_header Access-Control-Allow-Origin;
        proxy_hide_header Access-Control-Allow-Credentials;
        add_header 'Access-Control-Allow-Origin' $cors_origin always;
        add_header 'Access-Control-Allow-Credentials' 'true' always;

        proxy_pass http://gotrue:9999/;
        proxy_set_header Host gotrue.appflowy.homelab;
        proxy_pass_request_headers on;
    }
    ```

### 2. Host Directories
Ensure the following persistence and certificate paths are mounted on your Swarm nodes:
*   **Step-CA Cert:** `/mnt/docker-data/services/step-ca/certs/root_ca.crt` (mounted as read-only to allow containers to build trust with local SSL domains).

---

### 3. Database Search Path & Roles (For GoTrue and AppFlowy Cloud)
Because multiple services share the database, database search paths are managed at the role level to prevent query routing issues and conflicts.

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

### 3.1. Database Pre-initialization & Extensions
AppFlowy Cloud and GoTrue rely on specific PostgreSQL extensions (`vector` for AI embeddings, `uuid-ossp` for UUID generation, and `pgcrypto` for GoTrue's password hashing/encryption). 

Because the application users do not have superuser privileges to create extensions on-the-fly during migrations, these extensions and schemas must be **pre-initialized** by the database superuser (`postgres`) on the primary database container (`feee2dc85842`):

```sql
-- 1. Connect to the fresh database and enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 2. Pre-create the auth schema owned by gotrue to avoid race conditions
CREATE SCHEMA IF NOT EXISTS auth;
ALTER SCHEMA auth OWNER TO gotrue;

-- 3. Grant permissions to the appflowy user
GRANT ALL PRIVILEGES ON DATABASE appflowy TO appflowy;
GRANT ALL ON SCHEMA public TO appflowy;
GRANT USAGE, SELECT, REFERENCES ON ALL TABLES IN SCHEMA auth TO appflowy;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT SELECT, REFERENCES ON TABLES TO appflowy;
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
| `GOTRUE_DATABASE_URL` | GoTrue DB connection string (targeting auth schema) | `postgres://gotrue:<password>@pgpool:5432/appflowy` |
| `APPFLOWY_DATABASE_URL` | AppFlowy Cloud DB connection string | `postgres://appflowy:<password>@pgpool:5432/appflowy` |
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

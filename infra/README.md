# Infrastructure Stack

This directory contains the configurations for the **Infrastructure** stack of the homelab, deployed as a single Docker Swarm stack named `infra`. 

It hosts core management, network security, authentication, and internal certificate services, alongside the relational and NoSQL databases they depend on.

---

## Services Overview

### 1. Management & Control Plane
*   **Komodo Core** (`komodo`): The central control plane and dashboard for container and host management. Connects to `mongodb` as its database backend.
*   **Komodo Periphery** (`periphery`): Lightweight agent deployed globally to every node (`global` mode) to monitor hosts and manage local Docker containers. Connects back to Komodo Core via WebSockets (`ws://komodo:9120`).
*   **Docker Registry** (`registry`): Private container registry for self-hosted image distribution.

### 2. Ingress & Routing
*   **Nginx Proxy Manager** (`npm`): The frontend reverse proxy routing incoming HTTP/HTTPS traffic to internal services. Connects to PostgreSQL (`pgpool`) for configuration storage and utilizes `step-ca` for automatic TLS certificate provisioning.

### 3. Authentication & Security
*   **Authelia** (`authelia`): Single Sign-On (SSO) and authentication provider implementing OpenID Connect (OIDC) and 2FA. Connects to PostgreSQL (`pgpool`) for user session and state persistence.
*   **Step-CA** (`step-ca`): Private Certificate Authority managing internal certificates and running an ACME directory for internal services TLS.

### 4. Databases & Storage
*   **MinIO** (`minio`): High-performance S3-compatible object storage server.
*   **PostgreSQL HA Cluster** (`pgsql-primary`, `pgsql-standby`, `pgpool`, `pgbouncer`): A highly available PostgreSQL 17 cluster with native streaming replication (1 primary node, 2 standbys), Pgpool-II for query load-balancing/routing, and PgBouncer for transaction-level connection pooling.
    *   *Note:* PostgreSQL database nodes are configured for `max_connections=150`. PgBouncer is deployed in front of Pgpool-II to multiplex client connections (`PGBOUNCER_MAX_CLIENT_CONN=200`, `PGBOUNCER_DEFAULT_POOL_SIZE=3`), keeping Pgpool-II processes (`PGPOOL_NUM_INIT_CHILDREN=30`) and backend resources highly optimized and safe.
*   **MongoDB Replica Set** (`mongodb`): A global MongoDB 8 replica set cluster used by Komodo Core.

---

## Network Architecture

The stack defines the following overlay networks:
1.  `public` (Swarm: `infra_public`): An overlay network that connects all infrastructure services, including proxy routing, authentication, and databases. Any external services or stacks wishing to communicate with these services (such as databases or reverse proxy endpoints) must join the `infra_public` overlay network.
2.  `minio` (Swarm: `minio_net`): An overlay network dedicated to secure, isolated communication between MinIO storage and client applications (such as AppFlowy Cloud).

---

## Prerequisites & Setup

Ensure the following prerequisites are met before deploying the stack:

### 1. Docker Swarm Node Labeling
PostgreSQL expects the primary node to be explicitly labeled to host the primary DB replica:
```bash
docker node update --label-add pg=1 <primary-node-hostname>
```

### 2. Host Directories
Verify that the following persistence directories exist on the respective Docker host nodes:

*   **Komodo Core:** `/mnt/docker-data/services/komodo/keys`, `/mnt/docker-data/services/komodo/backups`, `/mnt/docker-data/services/komodo/repos`
*   **Komodo Periphery:** `/mnt/docker-data/services/periphery/<node-hostname>/keys`
*   **Step-CA:** `/mnt/docker-data/services/step-ca`
*   **Nginx Proxy Manager:** `/mnt/docker-data/services/nginx-proxy-manager/data`, `/mnt/docker-data/services/nginx-proxy-manager/letsencrypt`
    *   *Note:* Ensure the custom init script [99-trust-ca.sh](file:///Users/lflima/Vault/homelab/infra/nginx-proxy-manager/custom-init/99-trust-ca.sh) is copied to `/mnt/docker-data/services/nginx-proxy-manager/custom-init/99-trust-ca.sh` on the host.
*   **Docker Registry:** `/mnt/docker-data/services/registry`
*   **Authelia:** `/mnt/docker-data/services/authelia/config`
    *   *Note:* Copy [configuration.yml](file:///Users/lflima/Vault/homelab/infra/authelia/configuration.yml) and [users_database.yml](file:///Users/lflima/Vault/homelab/infra/authelia/users_database.yml) to the config path on the host.
*   **PostgreSQL:** `/opt/docker-data/databases/postgresql/data`, `/mnt/docker-data/services/postgresql/init/`
    *   *Note:* Copy [01-users-dbs.sh](file:///Users/lflima/Vault/homelab/infra/postgresql/01-users-dbs.sh) and [pg_hba_homelab.conf](file:///Users/lflima/Vault/homelab/infra/postgresql/pg_hba_homelab.conf) to the init path.
*   **Pgpool:** `/mnt/docker-data/services/pgpool/pool_passwd`
*   **MongoDB:** `/opt/docker-data/databases/mongodb/data`, `/opt/docker-data/databases/mongodb/config`
*   **MinIO:** `/mnt/docker-data/services/minio/data`

---

### 3. External Secrets Creation

Deploy all required Swarm secrets:

```bash
# Databases Secrets
echo "your_secure_pg_superuser_password" | docker secret create postgresql_superuser_password -
echo "your_secure_pg_replication_password" | docker secret create postgresql_replication_password -
echo "your_secure_pgpool_admin_password" | docker secret create pgpool_admin_password -
openssl rand -base64 32 | docker secret create pgpool_aes_key -
echo "mongodb_admin_user" | docker secret create mongodb_user -
echo "mongodb_admin_password" | docker secret create mongodb_password -
openssl rand -base64 756 | docker secret create mongodb_keyfile -

# Komodo Secrets
# Connection string targeting MongoDB replica set on public network:
echo "mongodb://komodo:your_komodo_password@mongodb-node1:27017,mongodb-node2:27017,mongodb-node3:27017/komodo?replicaSet=rs0&authSource=admin" | docker secret create komodo_db_uri -
openssl rand -base64 32 | tr -d '\n' | docker secret create komodo_jwt_secret -
openssl rand -base64 32 | tr -d '\n' | docker secret create komodo_webhook_secret -
echo "your_komodo_oidc_client_secret" | docker secret create komodo_oidc_client_secret -
# Komodo Periphery onboarding key (create one secret for each node)
echo "your_secure_onboarding_key" | docker secret create onboarding_vm-docker-adam -
echo "your_secure_onboarding_key" | docker secret create onboarding_vm-docker-zeus -
echo "your_secure_onboarding_key" | docker secret create onboarding_vm-docker-bragi -

# Step CA Secrets
echo "your_ca_password" | docker secret create step_ca_password -
cat path/to/root_ca.key | docker secret create step_ca_root_ca_key -
cat path/to/root_ca.crt | docker secret create step_ca_root_ca_crt -

# Nginx Proxy Manager Secrets
echo "npm_pg_password" | docker secret create npm_db_password -

# Registry Secrets
openssl rand -base64 32 | docker secret create registry_http_secret -
cat path/to/registry.htpasswd | docker secret create registry_htpasswd -

# Authelia Secrets
openssl rand -base64 32 | docker secret create authelia_jwt_secret -
openssl rand -base64 32 | docker secret create authelia_session_secret -
openssl rand -base64 32 | docker secret create authelia_storage_encryption_key -
echo "authelia_pg_password" | docker secret create authelia_db_password -
openssl rand -base64 32 | docker secret create authelia_oidc_hmac_secret -

# MinIO Secrets
echo "your_minio_root_user" | docker secret create minio_root_user -
echo "your_minio_root_password" | docker secret create minio_root_password -
```

---

## Deployment

Deploy the infrastructure stack with Docker Swarm:

```bash
docker stack deploy -c compose.yaml infra
```

---

## Verification & Post-Deployment

### 1. PostgreSQL HA Verification
Check database node status in the Pgpool router:
```bash
docker exec -it $(docker ps -q -f name=infra_pgpool) show pool_nodes;
```
Check replication status from PostgreSQL Primary:
```bash
docker exec -it $(docker ps -q -f name=infra_pgsql-primary) psql -U postgres -c "SELECT * FROM pg_stat_replication;"
```

### 2. MongoDB Replica Set Initialization
Once the containers are online, initiate the replica set (substituting your actual hostnames):
```bash
docker exec -it $(docker ps -q -f name=infra_mongodb) mongosh \
  --username $(cat /run/secrets/mongodb_user) \
  --password $(cat /run/secrets/mongodb_password) \
  --authenticationDatabase admin
```
Inside the prompt run:
```javascript
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongodb-<node1-hostname>:27017", priority: 2 },
    { _id: 1, host: "mongodb-<node2-hostname>:27017", priority: 1 },
    { _id: 2, host: "mongodb-<node3-hostname>:27017", priority: 1 }
  ]
})
```

### 3. Step-CA Health Check
```bash
docker exec -it $(docker ps -q -f name=infra_step-ca) step ca health --ca-url https://localhost:9000
```

### 4. Docker Registry Verification
Verify the registry is running and serving requests:
```bash
docker exec -it $(docker ps -q -f name=infra_registry) wget --no-verbose --spider http://localhost:5000/v2/ 2>&1
```

### 5. Authelia Health Check
Verify Authelia is running and its configuration is syntactically valid:
```bash
docker exec -it $(docker ps -q -f name=infra_authelia) authelia validate-config --config /config/configuration.yml
```

### 6. Komodo Core Status
Check connection to core dashboard:
```bash
docker service logs infra_komodo
```

### 7. Nginx Proxy Manager (NPM) Logs
Verify reverse proxy is listening on host interfaces:
```bash
docker service logs infra_npm
```

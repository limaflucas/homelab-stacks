# Databases Stack

This directory contains the consolidated configurations for all database and storage services in the homelab, deployed as a single Docker Swarm stack named `databases`.

The stack features its own internal overlay network, allowing isolated communication between backend databases and application containers, while exposing necessary endpoints for cluster replication and administrative access.

## Services Overview

### 1. PostgreSQL HA Cluster (with Pgpool-II & pgvector)
A highly available PostgreSQL database cluster utilizing native streaming replication for data redundancy and Pgpool-II for query routing, read load-balancing, and connection pool management.
*   **Version:** PostgreSQL 17 (Official Debian-based image) with `postgresql-17-pgvector` installed at startup on all db nodes.
*   **Topology:**
    *   **1 Primary node** (`pgsql-primary`): Runs on a designated primary Swarm node (enforced by `node.labels.pg == 1`). Handles all write queries.
    *   **2 Standby nodes** (`pgsql-standby`): Run on other Swarm nodes. On initial startup, they clone the primary database using `pg_basebackup` and subsequently follow the primary via streaming replication.
    *   **Pgpool-II** (`pgpool`): A load-balancer/proxy listening on port `5432`. It routes write queries to the primary and distributes read queries across standbys and primary.
*   **Authentication:** `scram-sha-256` for secure app logins, pgpool health checks, and replication.

### 2. MongoDB Replica Set
A high-performance MongoDB cluster configured as a replica set (`rs0`) for high availability.
*   **Version:** MongoDB 8
*   **Topology:** Distributed globally across all Swarm nodes (using `mode: global`).
*   **Security:** Enforces internal authentication using a shared MongoDB keyfile secret, alongside username/password authentication for clients.

### 3. MinIO Object Storage
An S3-compatible object storage server used for media and document assets.
*   **Version:** Latest MinIO Release
*   **Topology:** Standalone single-node, single-drive deployment.
*   **Endpoints:** API on port `9000` (internal), Console UI on port `9001` (internal).

### 4. Redis Cache
A fast, in-memory key-value store acting as a caching layer for applications like Outline and others.
*   **Version:** Redis 8 (Alpine-based)
*   **Topology:** Standalone cache node.

---

## Directory Structure

All configuration and initialization scripts are organized in subdirectories to keep them structured:

```text
databases/
├── compose.yaml          # The main Swarm compose stack file definition
├── README.md             # This documentation file
└── postgresql/
    ├── 01-users-dbs.sh   # DB init script (replication user & pgpool user setup)
    └── pg_hba_homelab.conf # Host-based authentication rules for PostgreSQL
```

---

## Prerequisites & Pre-deployment Steps

Before deploying the stack, perform the following administrative tasks on your Swarm manager:

### 1. Host Directories Creation
Ensure the following persistence directories exist on the respective Docker Swarm host nodes:

*   **PostgreSQL:**
    *   Data storage (all nodes): `/opt/docker-data/databases/postgresql/data`
    *   Init script: `/mnt/docker-data/databases/postgresql/init/01-users-dbs.sh` (copy from this repository)
    *   HBA config: `/mnt/docker-data/databases/postgresql/pg_hba_homelab.conf` (copy from this repository)
*   **Pgpool:**
    *   Passwords file: `/mnt/docker-data/databases/pgpool/pool_passwd` (Must be generated using `pg_md5` or `pg_enc` utilities)
*   **MongoDB:**
    *   Data storage: `/opt/docker-data/databases/mongodb/data`
    *   Config database: `/opt/docker-data/databases/mongodb/config`
*   **MinIO:**
    *   Data storage: `/mnt/docker-data/databases/minio/data`

### 2. Swarm Node Labeling
The PostgreSQL primary service (`pgsql-primary`) expects a primary node labeled with `pg=1` to run. Label your designated primary node:
```bash
docker node update --label-add pg=1 <primary-node-hostname>
```

For standbys, ensure other nodes do NOT have the `pg=1` label, as they are configured with:
```yaml
constraints:
  - node.labels.pg != 1
```

### 3. Creating Swarm Secrets
Deploy external secrets used by the databases stack:

```bash
# PostgreSQL & Pgpool Secrets
echo "your_secure_pg_superuser_password" | docker secret create postgresql_superuser_password -
echo "your_secure_pg_replication_password" | docker secret create postgresql_replication_password -
echo "your_secure_pgpool_admin_password" | docker secret create pgpool_admin_password -
openssl rand -base64 32 | docker secret create pgpool_aes_key -

# MinIO Secrets
echo "minio_admin_user" | docker secret create minio_root_user -
echo "minio_admin_password" | docker secret create minio_root_password -

# MongoDB Secrets
echo "mongodb_admin_user" | docker secret create mongodb_user -
echo "mongodb_admin_password" | docker secret create mongodb_password -
openssl rand -base64 756 | docker secret create mongodb_keyfile -
```

---

## Deployment

Deploy the combined databases stack using Docker Swarm:

```bash
docker stack deploy -c compose.yaml databases
```

The stack automatically creates a Swarm overlay network named `databases_default`. Other stacks in the homelab (e.g. apps, infra) can access these database services by joining the `databases_default` network as an external network:

```yaml
networks:
  databases_default:
    external: true
```

---

## Post-Deployment & Verification

### 1. PostgreSQL HA Verification

#### Check Streaming Replication Status (Run on Primary Node):
Run a query inside the primary container to see connected replication standbys:
```bash
docker exec -it $(docker ps -q -f name=databases_pgsql-primary) psql -U postgres -c "SELECT * FROM pg_stat_replication;"
```

#### Check Cluster Status via Pgpool:
Query the Pgpool container to view backend node states:
```bash
docker exec -it $(docker ps -q -f name=databases_pgpool) show pool_nodes;
```

---

### 2. MongoDB Replica Set Initialization
Once the MongoDB services are running, you must initialize the replica set.

1.  Access the MongoDB shell via one of the running MongoDB containers:
    ```bash
    docker exec -it $(docker ps -q -f name=databases_mongodb) mongosh \
      --username $(cat /run/secrets/mongodb_user) \
      --password $(cat /run/secrets/mongodb_password)
    ```

2.  Run the initiation command, substituting your actual Swarm hostnames:
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

3.  Verify the replica set status:
    ```javascript
    rs.status()
    ```

---

### 3. MinIO Health Check
Verify MinIO is healthy and running:
```bash
docker service logs databases_minio
```
You can query the health endpoint internally from any container on the `databases_default` network:
```bash
curl -f http://minio:9000/minio/health/live
```

---

### 4. Redis Cache Verification
Verify Redis connection:
```bash
docker exec -it $(docker ps -q -f name=databases_redis) redis-cli ping
```
Should return `PONG`.

---

## Application Connection Details

Applications deployed in other Swarm stacks connecting to these databases should configure their environment variables/settings as follows:

| Service | Hostname | Port | Credentials |
| :--- | :--- | :--- | :--- |
| **PostgreSQL** | `pgpool` | `5432` | Read/write routed through Pgpool load balancer |
| **MongoDB** | `mongodb-<hostname>` | `27017` | Standard replica set connection string format |
| **MinIO** | `minio` | `9000` (API) / `9001` (Console) | AWS S3 SDK compatible |
| **Redis** | `redis` | `6379` | Cache / Session store |

# PostgreSQL HA with Native Streaming Replication and Pgpool-II

This directory contains the configuration for a highly available PostgreSQL 17 cluster in Docker Swarm. It utilizes native PostgreSQL streaming replication for data consistency and Pgpool-II for load balancing and failover management.

## Goal

To provide a resilient, high-performance database cluster for the homelab, supporting automatic failover and read-load balancing for integrated services like Nginx Proxy Manager, Outline, and Vaultwarden.

## Architecture

- **PostgreSQL (Native)**: 3 nodes running the official `postgres:17` image.
  - **1 Primary**: Designated by the `pg=1` node label. Handles all writes and acts as the replication source.
  - **2 Standbys**: Distributed across other nodes. They automatically clone the primary using `pg_basebackup` on initial startup and follow via streaming replication.
- **Pgpool-II**: 3 nodes providing a single entry point (port 5432) for all applications.
  - **Load Balancing**: Distributes read queries across all healthy nodes.
  - **Failover**: Monitors backend health and manages connection routing.
- **Authentication**: `scram-sha-256` for all application and health-check connections.

## Provisioning

The cluster is automatically provisioned with the following databases and users via `01-users-dbs.sh`:

| Service | Database | User |
| :--- | :--- | :--- |
| **Nginx Proxy Manager** | `npm` | `npm` |
| **Outline** | `outline` | `outline` |
| **Vaultwarden** | `vaultwarden` | `vaultwarden` |
| **Replication** | `postgres` | `replicator` |
| **Health Check** | `postgres` | `pgpool` |

## Prerequisites

### 1. External Network
Ensure the `databases` network exists:
```bash
docker network create --driver overlay databases
```

### 2. Node Labeling
The primary node must be labeled to ensure it hosts the `pgsql-primary` service:
```bash
docker node update --label-add pg=1 <primary-node-hostname>
```

### 3. Secrets
The following external secrets are required:
```bash
echo "secure_password" | docker secret create postgresql_superuser_password -
echo "secure_password" | docker secret create postgresql_replication_password -
echo "secure_password" | docker secret create pgpool_admin_password -
```

### 4. Storage & Config
Ensure the following directories and files exist on the host nodes:
- **Data Path**: `/opt/docker-data/databases/postgresql/data`
- **Init Scripts**: `/mnt/docker-data/databases/postgresql/init/01-users-dbs.sh`
- **HBA Config**: `/mnt/docker-data/databases/postgresql/pg_hba_homelab.conf`

## Deployment

Deploy the stack:
```bash
docker stack deploy -c compose.yaml databases
```

## Verification

### Check Replication Status (on Primary)
```bash
docker exec -it $(docker ps -q -f name=databases_pgsql-primary) psql -U postgres -c "select * from pg_stat_replication;"
```

### Check Backend Status (via Pgpool)
```bash
docker exec -it $(docker ps -q -f name=databases_pgpool) show pool_nodes;
```

## Usage

Applications should connect to the `pgpool` service on port `5432`.
- **Host**: `pgpool`
- **Port**: `5432`
- **Auth Method**: `scram-sha-256`

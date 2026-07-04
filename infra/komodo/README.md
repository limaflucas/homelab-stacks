# Infrastructure: Komodo Core & Periphery

This directory contains the configuration for **Komodo**, the server and container management system for the homelab. It consists of:
- **Komodo Core**: The central control plane and dashboard.
- **Komodo Periphery**: The lightweight agent deployed globally to every node in the Swarm cluster.

## Architecture

### Komodo Core
- **Mode:** Docker Swarm Service (replicated, 1 replica)
- **Role:** Control Plane / Dashboard
- **Database:** Shared MongoDB Replica Set (in `databases/mongodb`)
- **Network:** Connected to `databases_internal` (for MongoDB) and `internet` (for proxy/internal communication).
- **Placement:** Restricted to a manager node for stable state management.

### Komodo Periphery
- **Mode:** Docker Swarm Service (`global` - one instance per node)
- **Role:** Remote Management Agent / System Monitoring
- **Connection:** Connects back to **Komodo Core** via WebSockets (`ws://komodo:9120`).
- **Identity:** Automatically identifies itself using the node's hostname (`{{.Node.Hostname}}`).
- **Network:** Connected to the `internet` overlay network.

## Installation Steps

### 1. Prepare external networks
Ensure the `databases` and `infra` overlay networks exist.
```bash
docker network create --driver overlay databases || true
docker network create --driver overlay infra || true
```

### 2. Prepare MongoDB User
Connect to the MongoDB primary and create the `komodo` user.

**Find the PRIMARY node:**
```bash
docker exec \
  $(docker ps -q -f name=databases_mongodb) \
  mongosh \
  --username $(cat /run/secrets/mongodb_user) \
  --password $(cat /run/secrets/mongodb_password) \
  --authenticationDatabase admin \
  --eval "rs.status().members.find(m => m.stateStr === 'PRIMARY').name"
```

**Connect and create the user:**
```bash
docker exec -it \
  $(docker ps -q -f name=databases_mongodb) \
  mongosh \
  --username $(cat /run/secrets/mongodb_user) \
  --password $(cat /run/secrets/mongodb_password) \
  --authenticationDatabase admin
```

Inside the `mongosh` prompt:
```javascript
use admin
db.createUser({
  user: "komodo",
  pwd: "your_komodo_password",
  roles: [
    { role: "dbOwner", db: "komodo" },
    { role: "clusterMonitor", db: "admin" }
  ]
})
```

### 3. Create External Secrets
Create the secrets required for the Komodo deployment.
```bash
# MongoDB Connection String
echo "mongodb://komodo:your_komodo_password@mongodb-node1:27017,mongodb-node2:27017,mongodb-node3:27017/komodo?replicaSet=rs0&authSource=admin" | docker secret create komodo_db_uri -

# JWT and Webhook Secrets
openssl rand -base64 32 | tr -d '\n' | docker secret create komodo_jwt_secret -
openssl rand -base64 32 | tr -d '\n' | docker secret create komodo_webhook_secret -
```

### 4. Deploy the Stack
```bash
docker stack deploy -c compose.yaml infra
```
This will deploy both the **Komodo Core** control plane and the **Komodo Periphery** agents to all nodes in the cluster.

### 5. Post-Deployment
Access the UI at `https://komodo.homelab` (configured via Nginx Proxy Manager) or directly at `http://<manager-ip>:9120`.

## Configuration Details

### Komodo Core
- **Persistence:**
    - Keys: `/mnt/docker-data/infra/komodo/keys` (contains `core.pub` and `peripheries.pub`)
    - Backups: `/mnt/docker-data/infra/komodo/backups`
- **Security:**
    - JWT and Webhook secrets are managed via Docker secrets and mounted to `/run/secrets`.
    - Periphery authentication uses the public key stored in `/config/keys/peripheries.pub`.

### Komodo Periphery
- **Core Communication:** 
    - Address: `ws://komodo:9120`
    - Public Key: Authenticates the Core using the public key located at `/config/keys/core.pub` (mounted from `infra/komodo`).
- **Persistence:** 
    - Uses a named volume `periphery_keys` for agent-specific key storage.
- **System Monitoring:** 
    - Mounts `/var/run/docker.sock` to manage containers.
    - Mounts `/proc` (read-only) for system metrics gathering.
- **TLS & Trust:** 
    - Mounts the internal Root CA from `infra/step-ca` to `/usr/local/share/ca-certificates/homelab-root-ca.crt` to establish trust for secure communications.
- **Timezone:** `America/Halifax`


# Infrastructure: Komodo Core

This directory contains the configuration for **Komodo Core**, the central control plane for server and container management in the homelab.

## Architecture

- **Mode:** Docker Swarm Service
- **Role:** Control Plane / Dashboard
- **Database:** Shared MongoDB Replica Set (in `databases/mongodb`)
- **Agents:** Managed via **Komodo Periphery** (deployed globally via `infra/periphery`)
- **Network:** Connected to `databases` (for MongoDB) and `infra` (for proxy/internal communication).
- **Placement:** Restricted to a **manager node** for stable state management.

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

# OIDC Client Secret (Optional - uncomment in compose.yaml if using Authelia)
# echo "your_oidc_secret" | docker secret create komodo_oidc_client_secret -
```

### 4. Deploy the Stack
```bash
docker stack deploy -c compose.yaml infra
```

### 5. Post-Deployment
Access the UI at `https://komodo.homelab` (configured via Nginx Proxy Manager) or directly at `http://<manager-ip>:9120`.

## Configuration Details

- **Persistence:**
    - Keys: `/mnt/docker-data/infra/komodo/keys`
    - Backups: `/mnt/docker-data/infra/komodo/backups`
- **TLS:** Trust is established using the internal Root CA certificate mounted to `/usr/local/share/ca-certificates/homelab-root-ca.crt`.
- **Periphery Agents:** The agents are deployed separately to every node in the Swarm. See `infra/periphery/README.md` for configuration details. Once deployed, they will connect back to this Core instance using the `PERIPHERY_CORE_ADDRESS`.

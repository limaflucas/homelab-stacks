# LLMs Stack

This directory contains the configurations for the **LLMs** stack of the homelab, deployed as a single Docker Swarm stack named `llms`. 

It hosts open-source LLM client interfaces and API proxy layers, connecting back to the centralized Ollama server running on `zeus.ollama.homelab`, and utilizing the high-availability PostgreSQL cluster (`pgpool:5432`) and MinIO (`minio:9000`) for robust, scalable data persistence.

---

## Services Overview

### 1. Web Interfaces
*   **Open WebUI** (`open-webui`): A feature-rich, highly customizable self-hosted web interface. Backed by PostgreSQL (`openwebui` database) for user accounts, chats, and configurations. Listen Port: `8080`.
*   **LobeChat** (`lobe-chat`): A modern, high-performance web client. Runs in full-stack database mode (`lobe-chat-database` image), utilizing PostgreSQL (`lobechat` database) for state, MinIO (`lobechat` bucket) for media/file uploads, and Authelia for OIDC user authentication. Listen Port: `3210`.

### 2. API Proxy & Router
*   **LiteLLM** (`litellm`): A lightweight API proxy standardizing LLM APIs to OpenAI-compatible endpoints. Backed by PostgreSQL (`litellm` database, using the `litellm-database` image) to enable user key generation, token usage logging, budgets, and rate limiting. Listen Port: `4000`.

---

## Network Architecture

The stack interacts with the following networks:
1.  `llms_private` (External: `llms_private`): A dedicated overlay network created by the `infra` stack securing traffic between the Nginx Proxy Manager and the containers in this stack.
2.  `pgpool` (External: `pgpool_net`): Connects all three services to the PostgreSQL HA router (`pgpool`) in the `infra` stack.
3.  `minio` (External: `minio_net`): Connects LobeChat directly to MinIO for file storage.

---

## Prerequisites & Setup

Ensure the following prerequisites are met before deploying the stack:

### 1. Host Directories & Mounts
Create the persistence and configuration directories on the Docker host:
*   **Open WebUI Data:** `/mnt/docker-data/services/open-webui/data`
*   **LiteLLM Config:** `/mnt/docker-data/services/litellm`

### 2. Copy Configuration Files
Copy the LiteLLM config file to the host path:
```bash
cp ./config/litellm-config.yaml /mnt/docker-data/services/litellm/config.yaml
```

### 3. PostgreSQL Database Setup
Log into your PostgreSQL HA cluster (e.g. via pgAdmin or `psql` running on the primary node) and run the following SQL to provision the databases and users:

```sql
-- Open WebUI
CREATE DATABASE openwebui;
CREATE USER openwebui WITH PASSWORD 'your_openwebui_db_password_here';
GRANT ALL PRIVILEGES ON DATABASE openwebui TO openwebui;

-- LiteLLM
CREATE DATABASE litellm;
CREATE USER litellm WITH PASSWORD 'your_litellm_db_password_here';
GRANT ALL PRIVILEGES ON DATABASE litellm TO litellm;

-- LobeChat
CREATE DATABASE lobechat;
CREATE USER lobechat WITH PASSWORD 'your_lobechat_db_password_here';
GRANT ALL PRIVILEGES ON DATABASE lobechat TO lobechat;
```
*(Note: LobeChat requires `pgvector` which is already installed on the cluster.)*

### 4. MinIO Bucket Creation
Log into the MinIO Console (`https://minio.homelab`) and create a new bucket named `lobechat`.

### 5. Authelia OIDC Client Registration
Add LobeChat as an OIDC client in Authelia's `configuration.yml`:
```yaml
identity_providers:
  oidc:
    clients:
      - client_id: lobechat
        client_name: LobeChat
        client_secret: '$pbkdf2-sha512$310000$c8p78n7pUMln0jzvd4aK4Q$JNRBzwAo0ek5qKn50cFzzvE9RXV88h1wJn5KGiHrD0YKtZaR/nCb2CJPOsKaPK0hjf.9yHxzQGZziziccp6Yng' # Hashed 'your_lobechat_authelia_client_secret_plaintext'
        public: false
        authorization_policy: one_factor
        redirect_uris:
          - https://lobechat.homelab/api/auth/callback/authelia
        scopes:
          - openid
          - profile
          - email
        userinfo_signed_response_alg: none
```

### 6. External Secrets Creation
Deploy the required Swarm secrets:

```bash
# Database Credentials
echo "openwebui" | docker secret create openwebui_db_user -
echo "your_openwebui_db_password_here" | docker secret create openwebui_db_password -

echo "litellm" | docker secret create litellm_db_user -
echo "your_litellm_db_password_here" | docker secret create litellm_db_password -

echo "lobechat" | docker secret create lobechat_db_user -
echo "your_lobechat_db_password_here" | docker secret create lobechat_db_password -

# LobeChat Secrets (MinIO and Security)
openssl rand -base64 32 | tr -d '\n' | docker secret create lobechat_key_vaults_secret -
openssl rand -base64 32 | tr -d '\n' | docker secret create lobechat_auth_secret -
echo "your_lobechat_authelia_client_secret_plaintext" | docker secret create authelia_lobechat_client_secret -
```

---

## Deployment

Deploy the `llms` stack using Docker Swarm:

```bash
docker stack deploy -c compose.yaml llms
```

---

## Verification & Troubleshooting

### 1. Check Service Status
```bash
docker stack services llms
```

### 2. View Service Logs
Verify that database migrations completed and services started:
```bash
docker service logs llms_open-webui
docker service logs llms_lobe-chat
docker service logs llms_litellm
```

### 3. Verify LiteLLM Wildcard Proxy
```bash
curl http://localhost:4000/v1/models
```

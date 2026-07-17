# LLMs Stack

This directory contains the configurations for the **LLMs** stack of the homelab, deployed as a single Docker Swarm stack named `llms`. 

It hosts the open-source client interface and API proxy layers, connecting back to the centralized Ollama server running on `zeus.ollama.homelab`, and utilizing the PostgreSQL cluster (`pgpool:5432`) for database persistence.

---

## Services Overview

### 1. Web Interfaces
*   **Open WebUI** (`open-webui`): A feature-rich, highly customizable self-hosted web interface. Backed by PostgreSQL (`openwebui` database) for user accounts, chats, and configurations. Listen Port: `8080`.

### 2. API Proxy & Router
*   **LiteLLM** (`litellm`): A lightweight API proxy standardizing LLM APIs to OpenAI-compatible endpoints. Backed by PostgreSQL (`litellm` database, using the `litellm-database` image) to enable user key generation, token usage logging, budgets, and rate limiting. Listen Port: `4000`.

---

## Network Architecture

The stack interacts with the following networks:
1.  `llms_private` (External: `llms_private`): A dedicated overlay network created by the `infra` stack securing traffic between the Nginx Proxy Manager and the containers in this stack.
2.  `pgpool` (External: `pgpool_net`): Connects both services to the PostgreSQL HA router (`pgpool`) in the `infra` stack.

---

## Prerequisites & Setup

Ensure the following prerequisites are met before deploying the stack:

### 1. Host Directories & Mounts
Create the configuration and persistence directories on the Docker host:
*   **LiteLLM Config:** `/mnt/docker-data/services/litellm`
*   **Open WebUI Uploads:** `/mnt/docker-data/services/open-webui/uploads`

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
```

### 4. Environment File (`.env`)
Create a `.env` file in the stack directory to define the required environment variables:
```env
LITELLM_DB_USER=litellm
LITELLM_DB_PASSWORD=your_litellm_db_password_here
LITELLM_MASTER_KEY=your_litellm_master_key_here

WEBUI_DB_USER=openwebui
WEBUI_DB_PASSWORD=your_openwebui_db_password_here
WEBUI_SECRET_KEY=your_webui_secret_key_here
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
```bash
docker service logs llms_open-webui
docker service logs llms_litellm
```

### 3. Verify LiteLLM Wildcard Proxy
```bash
curl http://localhost:4000/v1/models
```

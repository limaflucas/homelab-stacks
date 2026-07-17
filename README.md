# Homelab Project

Welcome to the Homelab project. This repository contains Docker Swarm and Docker Compose configurations for various self-hosted applications and infrastructure services, organized into logical categories.

## Directory Structure

### Apps
*   **[Grafana & Monitoring](./apps/grafana/README.md)**: Observability stack for collecting and visualizing metrics and logs (Grafana, VictoriaMetrics, VictoriaLogs, Alloy).
*   **[LLMs](./llms/README.md)**: Open WebUI (port `8080`) and LiteLLM (port `4000`).
*   **[Outline](./apps/outline/README.md)**: A modern team knowledge base and wiki.
*   **[Plex](./apps/plex/)**: Media server for streaming local content.

### Infrastructure
*   **[Komodo](./infra/komodo/README.md)**: Server and container management system (Control Plane & Periphery agents).
*   **[Nginx Proxy Manager](./infra/nginx-proxy-manager/README.md)**: Reverse proxy for managing access and SSL certificates, integrated with local CA.
*   **[Registry](./infra/registry/README.md)**: Private Docker registry for container image hosting.
*   **[Step-CA](./infra/step-ca/README.md)**: Private Certificate Authority for securing internal services with TLS.

### Databases
*   **[etcd](./databases/etcd/README.md)**: Highly available distributed key-value store, used as DCS for cluster coordination.
*   **[MongoDB](./databases/mongodb/README.md)**: A centralized shared MongoDB replica set.
*   **[PostgreSQL HA](./databases/postgresql/README.md)**: A highly available PostgreSQL cluster with native streaming replication and Pgpool-II.

### Security
*   **[Authelia](./security/authelia/README.md)**: Centralized authentication and Single Sign-On (SSO) provider.
*   **[Vaultwarden](./security/vaultwarden/README.md)**: Self-hosted password manager compatible with Bitwarden clients.

## Getting Started

To deploy a specific service, navigate to its respective directory, follow the setup instructions (like creating secret files, node labels, or configuring volumes) as detailed in its `README.md`, and run:

```bash
docker stack deploy -c compose.yaml <stack_name>
```
*Note: Most services in this repository are optimized for **Docker Swarm**.*

# Homelab Project

Welcome to the Homelab project. This repository contains Docker Compose configurations for various self-hosted applications and infrastructure services, organized into logical categories.

## Directory Structure

*   **[Databases: MongoDB](./databases/mongodb/README.md)**: A centralized shared MongoDB database for use by other services.
*   **[Infrastructure Management](./infra/management/README.md)**: Tools for managing the server and Docker containers (e.g., Komodo Core).
*   **[Infrastructure Monitoring](./infra/monitoring/README.md)**: Observability stack for collecting and visualizing metrics and logs (Grafana, VictoriaMetrics, VictoriaLogs, Alloy).
*   **[Infrastructure Proxy](./infra/proxy/README.md)**: Reverse proxy for managing access and SSL certificates (Nginx Proxy Manager).
*   **[Productivity: Outline](./productivity/outline/README.md)**: A modern team knowledge base and wiki (Outline, PostgreSQL, Redis, MinIO).
*   **[Security: Authelia](./security/authelia/README.md)**: Centralized authentication and Single Sign-On (SSO) provider (Authelia).
*   **[Security: Vaultwarden](./security/vaultwarden/README.md)**: Self-hosted password manager compatible with Bitwarden clients (Vaultwarden, PostgreSQL).

## Getting Started

To deploy a specific service, navigate to its respective directory, follow the setup instructions (like creating secret files or configuring `.env` variables) as detailed in its `README.md`, and run:

```bash
docker compose up -d
```

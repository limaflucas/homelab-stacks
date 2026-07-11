# Vaultwarden Stack

This directory contains the configurations for the **Vaultwarden** (Bitwarden password manager) stack of the homelab, deployed as a single Docker Swarm stack named `vaultwarden`. 

It hosts the secure password vault and integrates directly with the database router (`pgpool`) for user data persistence.

---

## Services Overview

### 1. Password Vault Manager
*   **Vaultwarden** (`vaultwarden`): Lightweight implementation of the Bitwarden API server written in Rust. Connects to PostgreSQL (`pgpool`) for database storage.

---

## Network Architecture

The stack interacts with two networks:
1.  `vaultwarden_private` (External: `vaultwarden_private`): A dedicated overlay network created by the `infra` stack, securing traffic between Nginx Proxy Manager and the Vaultwarden container.
2.  `pgpool` (External: `pgpool_net`): A dedicated database network. Connects Vaultwarden directly to the `pgpool` service in the `infra` stack.

---

## Prerequisites & Setup

Ensure the following prerequisites are met before deploying the stack:

### 1. Host Directories & Mounts
Verify that the following persistence directory exists on the Docker host:
*   **Vaultwarden Data:** `/mnt/docker-data/services/vaultwarden`

---

### 2. External Secrets Creation

Deploy all required Swarm secrets before launching the stack:

```bash
# PostgreSQL Database User & Password
echo "your_vaultwarden_db_user" | docker secret create vaultwarden_db_user -
echo "your_vaultwarden_db_password" | docker secret create vaultwarden_db_password -
```

---

## Deployment

Deploy the `vaultwarden` stack using Docker Swarm:

```bash
docker stack deploy -c compose.yaml vaultwarden
```

---

## Verification & Troubleshooting

### 1. Check Service Status
Monitor the status of the service in the stack:
```bash
docker stack services vaultwarden
```

### 2. View Service Logs
```bash
docker service logs vaultwarden_vaultwarden
```

### 3. Verify Database Connections
Check pgpool node status:
```bash
docker exec -it $(docker ps -q -f name=infra_pgpool) show pool_nodes;
```

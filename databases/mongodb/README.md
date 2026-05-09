# MongoDB

This directory contains the configuration for a shared MongoDB database instance, optimized for Docker Swarm.

## Goal

To provide a centralized and shared NoSQL database backend that can be consumed by multiple services within the homelab environment.

## Usage in Swarm

MongoDB is configured to store data and configuration on the host under `/mnt/docker-data/databases/mongodb/`. It uses **External Docker Secrets** for root credentials and is placed on a **manager node** to ensure stable persistence.

## Installation Steps

1.  **Create the external secrets:**
    ```bash
    echo "root_user" | docker secret create db_user -
    echo "your_secure_db_password" | docker secret create db_password -
    ```

2.  **Deploy the stack:**
    ```bash
    docker stack deploy -c compose.yaml databases
    ```

## Post-Deployment

- **Check health:**
  ```bash
  docker service ls | grep databases_mongodb
  ```
- **Connection String:**
  Other services on the `dockernet` network can connect using:
  `mongodb://<db_user>:<db_password>@mongodb:27017/`

## Configuration Details

- **Memory Cache:** Limited to 0.25GB WiredTiger cache.
- **Resources:** Limited to 0.5 CPU and 512M RAM.
- **Persistence:** Bound to `/mnt/docker-data/databases/mongodb/` on the manager node.
- **Network:** Connected to the external `dockernet` overlay network.

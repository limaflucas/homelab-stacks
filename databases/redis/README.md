# Redis

This directory contains the configuration for a standalone Redis instance, primarily used as a cache layer for other services.

## Architecture

- **Mode:** Standalone
- **Image:** `redis:7-alpine`
- **Networking:** Connected to the `databases` overlay network.
- **Persistence:** Data is stored on the host at `/opt/docker-data/databases/redis/data`.

## Installation Steps

1.  **Deploy the stack:**
    ```bash
    docker stack deploy -c compose.yaml databases
    ```

## Configuration Details
- **Resources:** Limited to 0.5 CPU and 256M RAM.

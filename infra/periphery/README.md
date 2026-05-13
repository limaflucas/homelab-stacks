# Infrastructure: Komodo Periphery

This directory contains the configuration for **Komodo Periphery**, the lightweight agent that runs on every node in the homelab to provide system monitoring and container management to the Komodo Core.

## Architecture

- **Mode:** Docker Swarm Service (`global`)
- **Role:** Management Agent / Monitoring
- **Deployment:** Automatically scales to every node in the Swarm cluster.
- **Connection:** Connects back to **Komodo Core** via WebSockets (`ws://komodo:9120`).
- **Identity:** Automatically identifies itself using the node's hostname (`{{.Node.Hostname}}`).
- **Network:** Connected to the `infra` overlay network.

## Installation Steps

1.  **Ensure Komodo Core is Running:**
    The Periphery agent requires a running instance of Komodo Core to connect to and retrieve its configuration.

2.  **Deploy the Stack:**
    The Periphery agent is typically deployed as part of the `infra` stack:
    ```bash
    docker stack deploy -c compose.yaml infra
    ```

## Configuration Details

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

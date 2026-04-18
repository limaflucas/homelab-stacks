# Infrastructure Management

This directory contains the configuration for the infrastructure management tools in this homelab.

## Tools Configured

*   **Komodo Core**: A server and container management tool (Control Plane).
*   **Komodo Periphery**: The agent that manages the host server and containers.

## Goal

To provide a web-based interface for managing Docker containers and server infrastructure across the homelab.

## Usage in this Project

Komodo is split into Core and Periphery. In this project:
- **Komodo Core** runs as a Docker container, storing its state in the shared MongoDB database (located in the root `/mongodb` directory). It exposes its interface on port `9120`.
- **Komodo Periphery** (the agent) also runs as a Docker container in the same stack, providing Core with access to manage the system's Docker socket and host.

## Installation Steps

1.  Ensure that the shared **MongoDB** service (in the `/mongodb` directory) is running and you have its credentials.
2.  Navigate to this directory:
    ```bash
    cd infra/komodo
    ```
3.  Create a `komodo.env` file for the Komodo configuration and credentials:
    ```bash
    cat <<EOF > komodo.env
    KOMODO_DATABASE_URI=mongodb://komodo:password@mongodb:27017/komodo?authSource=komodo
    TZ=America/Halifax

    KOMODO_FIRST_SERVER_NAME=Homelab
    KOMODO_HOST=http://komodo
    KOMODO_LOCAL_AUTH=false

    ## OIDC Login
    KOMODO_OIDC_ENABLED=true
    KOMODO_OIDC_PROVIDER=https://authelia.homelab
    KOMODO_OIDC_USE_FULL_EMAIL=true
    KOMODO_OIDC_CLIENT_ID=komodo
    KOMODO_OIDC_CLIENT_SECRET=secrete

    ## Periphery
    PERIPHERY_CORE_ADDRESS=http://komodo-core:9120
    PERIPHERY_CONNECT_AS=docker-vm
    PERIPHERY_ONBOARDING_KEY=YOUR_ONBOARDING_KEY
    PERIPHERY_CORE_PUBLIC_KEYS=file:/config/keys/core.pub
    PERIPHERY_ROOT_DIRECTORY=/etc/komodo
    EOF
    ```
    *Note: Replace `password`, `secrete`, `YOUR_ONBOARDING_KEY`, and URLs as necessary for your environment. Generate the onboarding key from the Komodo Core UI after logging in.*
4.  Start the container stack:
    ```bash
    docker compose up -d
    ```
5.  Access the Komodo Core interface at `http://<your-server-ip>:9120` to verify the Periphery agent is connected.

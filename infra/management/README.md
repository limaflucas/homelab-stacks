# Infrastructure Management

This directory contains the configuration for the infrastructure management tools in this homelab.

## Tools Configured

*   **Komodo Core**: A server and container management tool (Control Plane).

## Goal

To provide a web-based interface for managing Docker containers and server infrastructure across the homelab.

## Usage in this Project

Komodo is split into Core and Periphery. In this project:
- **Komodo Core** runs as a Docker container, storing its state in the shared MongoDB database (located in the root `/mongodb` directory). It exposes its interface on port `9120`.
- **Komodo Periphery** (the agent) is installed directly on the VM rather than as a container, allowing it native access to manage the system.

## Installation Steps

1.  Ensure that the shared **MongoDB** service (in the `/mongodb` directory) is running and you have its credentials.
2.  Navigate to this directory:
    ```bash
    cd infra/management
    ```
3.  Create a `komodo.env` file for the Komodo database credentials:
    ```bash
    echo "KOMODO_DATABASE_USERNAME=root_user" > komodo.env
    echo "KOMODO_DATABASE_PASSWORD=your_secure_db_password" >> komodo.env
    ```
4.  Start the container:
    ```bash
    docker compose up -d
    ```
5.  Access the Komodo Core interface at `http://<your-server-ip>:9120` and complete the initial sign-up.
6.  Install the **Komodo Periphery** agent directly on your VM according to the official Komodo documentation to link the host to the control plane.

# Networking: Nginx Proxy Manager

This directory contains the configuration for the reverse proxy.

## Tools Configured

*   **Nginx Proxy Manager (NPM)**: A reverse proxy management system based on NGINX, with a clean web UI.
*   **PostgreSQL**: The relational database used to store NPM's configuration.

## Goal

To easily expose web services on the network, manage domain routing, and handle SSL/TLS certificates using an internal Step-CA ACME server.

## Usage in this Project

NPM listens on the standard HTTP (`80`) and HTTPS (`443`) ports. It provides a web-based administration interface on port `81` to manage proxy hosts, redirection streams, and SSL certificates. The configuration is securely stored in the accompanying PostgreSQL database.

This setup is configured to use a local Step-CA server for ACME certificates, allowing for internal SSL without public DNS requirements.

## Installation Steps

1.  Navigate to this directory:
    ```bash
    cd networking/nginx-proxy-manager
    ```
2.  Ensure the external network `dockernet` exists:
    ```bash
    docker network create dockernet || true
    ```
3.  Create a `secrets` directory and the required secret files:
    ```bash
    mkdir -p secrets
    echo "your_secure_db_password" > secrets/db_password.txt
    echo "npm" > secrets/db_user.txt
    ```
4.  Create a `certs` directory and provide the Root CA certificate for Step-CA:
    ```bash
    mkdir -p certs
    # Copy your Step-CA root certificate
    cp /path/to/root_ca.crt certs/root_ca.crt
    ```
5.  Create a `.env` file for additional environment variables if needed.
6.  Start the proxy stack:
    ```bash
    docker compose up -d
    ```
7.  Access the Admin UI at `http://<your-server-ip>:81` to configure your proxies.

# Security: Vaultwarden

This directory contains the configuration for Vaultwarden, a Bitwarden-compatible password manager.

## Tools Configured

*   **Vaultwarden**: An alternative implementation of the Bitwarden server API written in Rust, ideal for self-hosted deployments.
*   **PostgreSQL**: The relational database used to store Vaultwarden's encrypted data.

## Goal

To provide a secure, self-hosted password and secret management solution compatible with official Bitwarden clients.

## Usage in this Project

Vaultwarden is deployed alongside a PostgreSQL database for reliable data storage. It is configured to allow new user signups (`SIGNUPS_ALLOWED=true`). The web vault interface and the API for clients are exposed on port `8080`.

## Installation Steps

1.  Navigate to this directory:
    ```bash
    cd security/vaultwarden
    ```
2.  Create a `secrets` directory and the required database credentials:
    ```bash
    mkdir -p secrets
    echo "your_secure_db_password" > secrets/db_password.txt
    echo "vaultwarden_user" > secrets/db_user.txt
    ```
3.  Start the Vaultwarden stack:
    ```bash
    docker compose up -d
    ```
4.  Access the web vault at `http://<your-server-ip>:8080` to create your account and manage passwords. *Note: Vaultwarden generally requires HTTPS to be used from web browsers, so it should be placed behind a reverse proxy.*

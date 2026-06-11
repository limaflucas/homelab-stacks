# Apps: Outline Wiki

This directory contains the configuration for the Outline knowledge base.

## Tools Configured

*   **Outline**: A fast, collaborative, modern knowledge base for teams.
*   **PostgreSQL**: Dedicated database instance for Outline.

*(Note: Redis and MinIO have been migrated to standalone services in the `databases` directory).*

## Goal

To provide a robust, self-hosted Wiki and knowledge management system with rich features, secure authentication, and scalable storage.

## Usage in this Project

Outline is configured as a partially standalone stack. It relies on a dedicated Postgres container for relational data, but now connects to the central Swarm Redis and MinIO clusters located in `databases/`. Authentication is handled via the external Authelia container for Single Sign-On (SSO) via OIDC. The Outline application itself is exposed on port `3001`.

## Installation Steps

1.  Navigate to this directory:
    ```bash
    cd apps/outline
    ```
2.  Create the `secrets` directory and populate the required files:
    ```bash
    mkdir -p secrets
    echo "your_db_password" > secrets/db_password.txt
    echo "outline_user" > secrets/db_user.txt
    ```
3.  Ensure you have a `.env` file configured for Outline (refer to Outline documentation). **Crucially, update your `.env` to point to the new standalone `redis` and `minio` hostnames on the `databases_internal` network.**
4.  Generate or place the required SSL certificates in a `certs/` directory, specifically creating the combined CA file as noted in the docker-compose (`cat ./certs/outline-pgsql.crt /path/to/authelia.crt > ./certs/combined-ca.crt`).
5.  Start the stack:
    ```bash
    docker compose up -d
    ```
7.  Access Outline at `http://<your-server-ip>:3001` (or via your configured proxy).

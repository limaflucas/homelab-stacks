# Security: Authelia

This directory contains the configuration for Authelia, an open-source authentication and authorization server.

## Tools Configured

*   **Authelia**: An open-source authentication and authorization server (OIDC provider).

## Goal

To provide a centralized authentication and Single Sign-On (SSO) provider for various homelab services, such as Outline and Komodo.

## Usage in this Project

Authelia is configured as an independent service on the `infra_internet` network. It provides OIDC capabilities and is accessible on port `9091`. 

### Key Features:
- **Centralized Auth:** Protects `*.homelab` subdomains.
- **OIDC Provider:** Configured for **Outline Wiki** and **Komodo Core**.
- **File-based Users:** Uses `users_database.yml` for user management.
- **PostgreSQL Storage:** Stores session and persistent data in the central PostgreSQL cluster.

## Installation Steps

1.  **Prepare PostgreSQL Database:**
    Connect to your PostgreSQL primary and create the `authelia` user and database.
    ```sql
    CREATE USER authelia WITH PASSWORD 'your_secure_password' LOGIN;
    CREATE DATABASE authelia OWNER authelia;
    ```

2.  **Generate Secrets:**
    Authelia in this project is configured to use **Docker Secrets** (`external: true`). You must create these secrets in your Swarm cluster before deploying.

    ```bash
    # 1. Generate random strings for system secrets
    docker run --rm authelia/authelia:latest authelia crypto rand --length 64 --charset alphanumeric | docker secret create authelia_jwt_secret -
    docker run --rm authelia/authelia:latest authelia crypto rand --length 64 --charset alphanumeric | docker secret create authelia_session_secret -
    docker run --rm authelia/authelia:latest authelia crypto rand --length 64 --charset alphanumeric | docker secret create authelia_storage_encryption_key -
    docker run --rm authelia/authelia:latest authelia crypto rand --length 64 --charset alphanumeric | docker secret create authelia_oidc_hmac_secret -

    # 2. Create the Database Password secret
    echo "your_secure_postgres_password" | docker secret create authelia_db_password -

    # 3. Generate RSA Private Key for OIDC (Note: In 4.38+, JWKS is preferred)
    # This command generates a clean PEM file suitable for Docker Secrets.
    docker run --rm authelia/authelia:latest authelia crypto pair rsa generate --bits 2048 --file.private-key /dev/stdout --file.public-key /dev/null | tr -d '\r' > oidc_key.pem
    docker secret create authelia_oidc_issuer_private_key oidc_key.pem
    rm oidc_key.pem
    ```

3.  **Generate OIDC Client Secrets:**
    OIDC client secrets should be **hashed** inside `configuration.yml`. Generate a secret and its hash for each client (Outline and Komodo):
    ```bash
    docker run --rm authelia/authelia:latest authelia crypto hash generate pbkdf2 --variant sha512 --random --random.length 72 --random.charset rfc3986
    ```
    *   **Random Password**: Copy this into your application's config (e.g., `outline.env` or Komodo UI).
    *   **Digest**: Copy this into `configuration.yml` under `identity_providers.oidc.clients.secret`.

4.  **Configure Users:**
    Generate a password hash for your users in `users_database.yml`.
    ```bash
    docker run --rm authelia/authelia:latest authelia crypto hash generate pbkdf2 --variant sha512 --password yourpassword
    ```

5.  **Deploy Files:**
    Place `configuration.yml` and `users_database.yml` in `/mnt/docker-data/security/authelia/config`. Note that `configuration.yml` is also used as a Docker Secret.

6.  **Start Authelia:**
    ```bash
    cd security/authelia
    docker stack deploy -c compose.yaml authelia
    ```

## Application Integration

### Outline Wiki
In your `outline.env`, add:
```env
OIDC_CLIENT_ID=outline
OIDC_CLIENT_SECRET=your_generated_client_secret
OIDC_AUTH_URI=https://auth.homelab/api/oidc/authorization
OIDC_TOKEN_URI=https://auth.homelab/api/oidc/token
OIDC_USERINFO_URI=https://auth.homelab/api/oidc/userinfo
OIDC_SCOPES=openid profile email groups
```

### Komodo Core
In the Komodo UI, configure OIDC with:
- **Issuer:** `https://auth.homelab`
- **Client ID:** `komodo`
- **Client Secret:** `your_generated_client_secret`
- **Redirect URI:** `https://komodo.homelab/api/auth/callback/oidc`

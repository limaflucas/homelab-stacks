# Security: Authelia

This directory contains the configuration for Authelia, an open-source authentication and authorization server.

## Tools Configured

*   **Authelia**: An open-source authentication and authorization server (OIDC provider).

## Goal

To provide a centralized authentication and Single Sign-On (SSO) provider for various homelab services, such as Outline and Komodo.

## Usage in this Project

Authelia is configured as an independent service on the `dockernet` network. It provides OIDC capabilities and is accessible on port `9091`. The configuration files (`configuration.yml` and `users_database.yml`) should be provided in the mapped volume directory.

## Installation Steps

1.  Navigate to this directory:
    ```bash
    cd security/authelia
    ```
2.  Provide the necessary `configuration.yml` and `users_database.yml` files in `/mnt/docker-data/security/authelia`.
3.  Start the Authelia container:
    ```bash
    docker compose up -d
    ```
4.  Configure other services (like Outline or Komodo) to use Authelia as their OIDC provider.

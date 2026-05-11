# Infrastructure: Nginx Proxy Manager

This directory contains the configuration for **Nginx Proxy Manager (NPM)**, optimized for Docker Swarm.

## Architecture

- **Mode:** Docker Swarm Service
- **Role:** Reverse Proxy / SSL Termination
- **Network:** 
    - `infra`: For internal communication with other services (including Step-CA for ACME).
- **Placement:** Restricted to a **manager node** to manage ingress and certificates consistently.

## Installation Steps

1.  **Deploy the Stack:**
    ```bash
    docker stack deploy -c compose.yaml infra
    ```

2.  **Post-Deployment:**
    - Access the Admin UI at `http://<manager-ip>:81`.
    - Default credentials: `admin@example.com` / `changeme`.
    - Configure Step-CA as your ACME server using the endpoint: `https://step-ca:9000/acme/acme/directory`.

## Configuration Details

- **Persistence:**
    - Data: `/mnt/docker-data/infra/nginx-proxy-manager/data`
    - Certificates: `/mnt/docker-data/infra/nginx-proxy-manager/letsencrypt`
- **TLS & Trust:** 
    - Internal trust is established by mounting the Homelab Root CA from `infra/step-ca` to `/usr/local/share/ca-certificates/homelab-root-ca.crt`.
    - A custom initialization script `99-trust-ca.sh` is used to update the CA store within the container.
- **ACME:** Pre-configured to use the internal Step-CA ACME directory (`LE_SERVER`).
- **Ports:** 
    - 80: HTTP
    - 443: HTTPS
    - 81: Admin UI
- **Environment:**
    - `DISABLE_IPV6: 'true'`
    - `TZ: 'America/Halifax'`

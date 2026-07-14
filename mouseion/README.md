# Mouseion Stack

This directory contains the configurations for the **Mouseion** (Media & Entertainment) stack of the homelab, deployed as a single Docker Swarm stack named `mouseion`. 

It hosts all media sourcing, index management, downloading, request handling, and private VPN network routing.

---

## Services Overview

### 1. Networking & Privacy
*   **Gluetun VPN Client** (`gluetun`): Lightweight WireGuard VPN client (NordVPN) running in userspace, securing outbound connections for downloading services.
*   **Gluetun SOCKS Proxy** (`gluetun-socks`): SOCKS5 proxy (gost) that forwards local network requests through the VPN tunnel.

### 2. Sourcing & Library Management
*   **Radarr** (`radarr`): Automated movie downloader. Connects to PostgreSQL (`pgbouncer`) for database storage.
*   **Sonarr** (`sonarr`): Automated TV series and anime downloader. Connects to PostgreSQL (`pgbouncer`) for database storage.
*   **Prowlarr** (`prowlarr`): Torrent and Usenet indexer manager. Connects to Radarr and Sonarr to sync indexers.

### 3. Request & Discovery
*   **Seerr** (`seerr`): Request management front-end (Overseerr) for Plex users. Connects to PostgreSQL (`pgbouncer`) for library request databases.

### 4. Downloader
*   **SABnzbd** (`sabnzbd`): High-performance Usenet downloader. Routes its outbound downloads through the `gluetun` VPN container to ensure secure, private downloads.

---

## Network Architecture

The stack interacts with two networks:
1.  `mouseion_private` (External: `mouseion_private`): A dedicated overlay network created by the `infra` stack, securing traffic between Nginx Proxy Manager, Seerr, Sonarr, Radarr, Prowlarr, SABnzbd, and Gluetun.
2.  `pgpool` (External: `pgpool_net`): A dedicated database network. Connects `radarr`, `sonarr`, and `seerr` directly to the `pgbouncer` service in the `infra` stack.

---

## Prerequisites & Setup

Ensure the following prerequisites are met before deploying the stack:

### 1. Host Directories & Mounts
Verify that the following persistence directories and media storage paths exist on the respective Docker host nodes:

*   **Gluetun:** `/mnt/docker-data/services/gluetun`
*   **Prowlarr:** `/mnt/docker-data/services/prowlarr/config`
*   **Radarr:** `/mnt/docker-data/services/radarr/config`, `/mnt/pirateflix/media/movies`, `/mnt/pirateflix/downloads/complete`
*   **SABnzbd:** `/mnt/docker-data/services/sabnzbd/config`, `/mnt/pirateflix/downloads/incomplete`, `/mnt/pirateflix/downloads/complete`
*   **Seerr:** `/mnt/docker-data/services/seerr/config`
*   **Sonarr:** `/mnt/docker-data/services/sonarr/config`, `/mnt/pirateflix/media/tv`, `/mnt/pirateflix/media/animes`, `/mnt/pirateflix/downloads/complete`

---

### 2. External Secrets Creation

Deploy all required Swarm secrets before launching the stack:

```bash
# VPN Credentials & Keys
echo "your_vpn_countries" | docker secret create vpn_countries -
echo "your_wireguard_private_key" | docker secret create vpn_private_key -

# PostgreSQL Database Passwords
echo "your_radarr_db_password" | docker secret create radarr_database_password -
echo "your_seerr_db_password" | docker secret create seerr_db_password -
echo "your_sonarr_db_password" | docker secret create sonarr_database_password -
```

---

## Deployment

Deploy the `mouseion` stack using Docker Swarm:

```bash
docker stack deploy -c compose.yaml mouseion
```

---

## Verification & Troubleshooting

### 1. Check Service Status
Monitor the status of all services in the stack:
```bash
docker stack services mouseion
```

### 2. View Service Logs
*   **Gluetun:**
    ```bash
    docker service logs mouseion_gluetun
    ```
*   **Radarr:**
    ```bash
    docker service logs mouseion_radarr
    ```
*   **Sonarr:**
    ```bash
    docker service logs mouseion_sonarr
    ```
*   **SABnzbd:**
    ```bash
    docker service logs mouseion_sabnzbd
    ```
*   **Seerr:**
    ```bash
    docker service logs mouseion_seerr
    ```

### 3. Verify Database Connections
Check if pgpool node status is correct and resolving:
```bash
docker exec -it $(docker ps -q -f name=infra_pgpool) show pool_nodes;
```

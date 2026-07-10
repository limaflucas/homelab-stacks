# Media: Sonarr

This directory contains the configuration for **Sonarr**, a PVR for Usenet and BitTorrent users. It can monitor multiple RSS feeds for new episodes of your favorite shows and will grab, sort, and rename them.

## Architecture

- **Mode:** Docker Swarm Service
- **Role:** TV Show Management / PVR
- **Image:** `lscr.io/linuxserver/sonarr:latest`
- **Networking:** 
    - **Internal Network:** Connected to `infra_media-internal` to communicate with other media apps (Prowlarr, Sabnzbd, etc.).
    - **Database Network:** Connected to `databases_internal` for PostgreSQL access.
- **Placement:** Restricted to a **manager node** for stable lifecycle management and persistence.

## Features

- **Automated Management:** Automatically monitors RSS feeds for new episodes and grabs them.
- **Library Organization:** Automatically sorts and renames downloaded files.
- **Persistence:** Configuration, database, and library metadata are stored in `/mnt/docker-data/media/sonarr/config`.
- **Database Support:** Configured to use PostgreSQL (via Docker Secrets for credentials).
- **DNS Strategy:** Uses a custom entrypoint to dynamically discover and use Gluetun's Virtual IP. It prepends the content of `/mnt/docker-data/media/resolv.conf` (mounted as `/etc/resolv.conf.base`) to the final `/etc/resolv.conf` before adding the VPN's nameserver.

## Installation Steps

### 1. Ensure Networks and Base Files Exist
Make sure the required overlay networks and the base DNS configuration file are created:
```bash
docker network create --driver overlay infra_media-internal || true
docker network create --driver overlay databases_internal || true
# Ensure the base resolv.conf exists on the host
touch /mnt/docker-data/media/resolv.conf
```

### 2. Create Database Secret
Create the secret for the Sonarr database password:
```bash
echo "your_sonarr_db_password" | docker secret create sonarr_database_password -
```

### 3. Deploy the Stack
Deploy Sonarr as part of your media stack:
```bash
docker stack deploy -c compose.yaml media
```

## Usage

Access the Sonarr UI at:
`http://<manager-ip>:8989`

## Configuration Details

- **Timezone:** `America/Halifax`
- **User/Group ID:** `1000:1000` (Standard for LinuxServer images)
- **Persistence:** 
    - Config: `/mnt/docker-data/media/sonarr/config` mapped to `/config`
    - TV Library: `/mnt/pirateflix/media/tv` mapped to `/tv`
    - Downloads: `/mnt/pirateflix/downloads/complete` mapped to `/downloads`
    - Base DNS: `/mnt/docker-data/media/resolv.conf` mapped to `/etc/resolv.conf.base`
- **DNS Strategy:** Dynamic `/etc/resolv.conf` injection via Gluetun VIP discovery, based on a persistent host file.
- **Resources:** Limited to 0.5 CPU and 1G Memory.

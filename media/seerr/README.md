# Media: Seerr

This directory contains the configuration for **Seerr**, a free and open-source media request and discovery manager that unifies **Overseerr** and **Jellyseerr**.

## Architecture

- **Mode:** Docker Swarm Service
- **Role:** Media Request & Discovery Manager
- **Image:** `ghcr.io/seerr-team/seerr:latest`
- **Networking:** 
    - **Internal Network:** Connected to `infra_media-internal` to communicate with your media server (Plex, Jellyfin, etc.) and PVR apps (Sonarr, Radarr).
- **Placement:** Restricted to a **manager node** for stable lifecycle management and persistence.

## Features

- **Multi-Server Support:** Works with Plex, Jellyfin, and Emby.
- **Automation:** Integrates with Sonarr and Radarr to automate fulfillment of user requests.
- **User Discovery:** Modern interface for users to discover and request content without needing direct access to your media library managers.
- **Persistence:** All configuration files (excluding the database) are stored in `/mnt/docker-data/media/seerr/config`.
- **Database:** Uses a centralized **PostgreSQL** instance via `pgpool`.

## Installation Steps

### 1. Ensure Networks Exist
Make sure the required overlay networks are created:
```bash
docker network create --driver overlay infra_media-internal || true
docker network create --driver overlay databases || true
```

### 2. Create Database Secrets
Create the secret for the PostgreSQL user:
```bash
echo "your_seerr_db_password" | docker secret create seerr_db_password -
```

### 3. Prepare Permissions
Seerr runs as UID `1000`. Ensure the config directory has the correct ownership on the host:
```bash
sudo chown -R 1000:1000 /mnt/docker-data/media/seerr/config
```

### 4. Deploy the Stack
Deploy Seerr as part of your media stack:
```bash
docker stack deploy -c compose.yaml media
```

## Usage

Access the Seerr UI at:
`http://<manager-ip>:5055`

During the initial setup wizard, you will be prompted to connect your media server and configure your Sonarr/Radarr instances.

## Configuration Details

- **Timezone:** `America/Halifax`
- **Port:** `5055`
- **Database:** PostgreSQL (via `pgpool` on the `databases` network).
- **Persistence:** `/mnt/docker-data/media/seerr/config` mapped to `/app/config`
- **Resources:** Limited to 0.5 CPU and 1GB Memory.
- **Healthcheck:** Monitored via the Seerr status API endpoint.

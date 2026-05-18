# Media: Radarr

This directory contains the configuration for **Radarr**, a movie manager for Usenet and BitTorrent users. It can monitor multiple RSS feeds for new movies and will grab, sort, and rename them.

## Architecture

- **Mode:** Docker Swarm Service
- **Role:** Movie Management / PVR
- **Image:** `lscr.io/linuxserver/radarr:latest`
- **Networking:** 
    - **Internal Network:** Connected to `infra_media-internal` to communicate with other media apps (Prowlarr, Sabnzbd, etc.).
    - **Database Network:** Connected to `databases_internal` for PostgreSQL access.
- **Placement:** Restricted to a **manager node** for stable lifecycle management and persistence.

## Features

- **Automated Management:** Automatically monitors RSS feeds for new movies and grabs them.
- **Library Organization:** Automatically sorts and renames downloaded files.
- **Persistence:** Configuration, database, and library metadata are stored in `/mnt/docker-data/media/radarr/config`.
- **Database Support:** Configured to use PostgreSQL (via Docker Secrets for credentials).

## Installation Steps

### 1. Ensure Networks Exist
Make sure the required overlay networks are created:
```bash
docker network create --driver overlay infra_media-internal || true
docker network create --driver overlay databases_internal || true
```

### 2. Create Database Secret
Create the secret for the Radarr database password:
```bash
echo "your_radarr_db_password" | docker secret create radarr_database_password -
```

### 3. Deploy the Stack
Deploy Radarr as part of your media stack:
```bash
docker stack deploy -c compose.yaml media
```

## Usage

Access the Radarr UI at:
`http://<manager-ip>:7878`

## Configuration Details

- **Timezone:** `America/Halifax`
- **User/Group ID:** `1000:1000` (Standard for LinuxServer images)
- **Persistence:** 
    - Config: `/mnt/docker-data/media/radarr/config` mapped to `/config`
    - Movie Library: `/mnt/pirateflix/media/movies` mapped to `/movies`
    - Downloads: `/mnt/pirateflix/downloads/complete` mapped to `/downloads`
- **Resources:** Limited to 0.5 CPU and 512M Memory.

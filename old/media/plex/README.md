# Media: Plex

This directory contains the configuration for **Plex Media Server**, the heart of your home media center.

## Architecture

- **Mode:** Docker Swarm Service
- **Role:** Media Server & Transcoder
- **Image:** `lscr.io/linuxserver/plex:latest`
- **Networking:** 
    - **Host Mode Port:** Port `32400` is exposed in `host` mode to ensure Plex can discover other devices on your local network (GDM/DLNA).
    - **Internal Network:** Connected to `infra_media-internal` for communication with other media tools if needed.
- **Placement:** Restricted to a **manager node** for stable lifecycle management and high-speed metadata access.

## Features

- **Secrets Management:** The `PLEX_CLAIM` token is managed securely via Docker Secrets.
- **Library Integration:** Directly mapped to the `/mnt/pirateflix/media` folders used by Sonarr and Radarr.
- **Optimized Transcoding:** Includes a dedicated `/transcode` volume.

## Installation Steps

### 1. Obtain a Plex Claim Token
Go to [plex.tv/claim](https://www.plex.tv/claim) and copy your token. It is only valid for 4 minutes.

### 2. Create the Secret
Create the Docker secret on your manager node:
```bash
echo "claim-xxxxxxxxxxxx" | docker secret create plex_claim -
```

### 3. Deploy the Stack
Deploy Plex as part of your media stack:
```bash
docker stack deploy -c compose.yaml media
```

## Configuration Details

- **Timezone:** `America/Halifax`
- **User/Group ID:** `1000:1000`
- **Persistence:** 
    - Config: `/mnt/docker-data/apps/plex/config`
    - TV Library: `/mnt/pirateflix/media/tv`
    - Movie Library: `/mnt/pirateflix/media/movies`
    - Transcode: `/mnt/docker-data/apps/plex/transcode`
- **Resources:** 2.0 CPU / 2GB Memory.

## Note on Hardware Acceleration
This configuration does not include hardware acceleration by default because Docker Swarm does not natively support the `devices` key. To enable Intel QuickSync or NVIDIA HWA, you will need to apply node-specific labels and use a workaround (like a device mapping manager) or pin the service to a specific node with volume-mapped drivers.

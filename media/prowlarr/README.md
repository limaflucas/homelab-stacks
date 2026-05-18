# Media: Prowlarr

This directory contains the configuration for **Prowlarr**, an indexer manager/proxy built on the popular *arr .net/reactjs base stack to integrate with your various PVR apps.

## Architecture

- **Mode:** Docker Swarm Service
- **Role:** Indexer Manager / Proxy
- **Image:** `lscr.io/linuxserver/prowlarr:latest`
- **Networking:** 
    - **Infra Network:** Connected to `infra` for proxy access (Gluetun) and external connectivity.
    - **Internal Network:** Connected to `media-internal` to communicate with other media apps (Sonarr, Radarr, etc.).
- **Placement:** Restricted to a **manager node** for stable lifecycle management and persistence.

## Features

- **VPN Routing:** Configured to use **Gluetun** as an HTTP/HTTPS proxy to ensure all indexer traffic is routed through the VPN.
- **Centralized Management:** Supports Usenet and BitTorrent indexers, and syncs them across all your *arr apps.
- **Persistence:** Configuration and database are stored in `/mnt/docker-data/media/prowlarr`.

## Installation Steps

### 1. Ensure Networks Exist
Make sure the required overlay networks are created:
```bash
docker network create --driver overlay infra || true
docker network create --driver overlay media-internal || true
```

### 2. Deploy the Stack
Deploy Prowlarr as part of your media stack:
```bash
docker stack deploy -c compose.yaml media
```

## Usage

Access the Prowlarr UI at:
`http://<manager-ip>:9696`

### Configuring Proxy in Prowlarr
The service is already configured with `HTTP_PROXY` and `HTTPS_PROXY` environment variables. Prowlarr should automatically use these for connecting to indexers. You can verify this in the **Settings > General > Proxy** section of the UI.

## Configuration Details

- **Timezone:** `America/Halifax`
- **User/Group ID:** `1000:1000` (Standard for LinuxServer images)
- **Persistence:** `/mnt/docker-data/media/prowlarr` mapped to `/config`
- **Resources:** Limited to 0.5 CPU and 512M Memory.

# Media: SABnzbd

SABnzbd is a multi-platform binary newsreader. It makes downloading from Usenet as simple and streamlined as possible by automating almost all tasks.

## Architecture

- **Mode:** Docker Swarm Service
- **Role:** Usenet Downloader
- **Image:** `lscr.io/linuxserver/sabnzbd:latest`
- **Networking:** 
    - **Internal Network:** Connected to `infra_media-internal` to communicate with other media apps (Prowlarr, Sonarr, Radarr, etc.).
- **Placement:** Restricted to a **manager node** for stable lifecycle management and persistence.

## Features

- **Automated Usenet Downloading:** Simplifies the process of downloading binary data from Usenet.
- **VPN DNS Strategy:** Uses a custom entrypoint to dynamically discover and use Gluetun's Virtual IP as its primary DNS nameserver, ensuring secure name resolution through the VPN.
- **Persistence:** 
    - Config: `/mnt/docker-data/media/sabnzbd/config`
    - Downloads: `/mnt/pirateflix/downloads`

## Installation Steps

### 1. Ensure Networks Exist
Make sure the required overlay networks are created:
```bash
docker network create --driver overlay infra_media-internal || true
```

### 2. Deploy the Stack
Deploy SABnzbd as part of your media stack:
```bash
docker stack deploy -c compose.yaml media
```

## Usage

Access the SABnzbd UI at:
`http://<manager-ip>:8080`

## Configuration Details

- **Timezone:** `America/Halifax`
- **User/Group ID:** `1000:1000` (Standard for LinuxServer images)
- **Persistence:** 
    - Config: `/mnt/docker-data/media/sabnzbd/config` mapped to `/config`
    - Incomplete Downloads: `/mnt/pirateflix/downloads/incomplete` mapped to `/config/Downloads/incomplete`
    - Complete Downloads: `/mnt/pirateflix/downloads/complete` mapped to `/config/Downloads/complete`
- **Resources:** Limited to 1.0 CPU and 512M Memory.

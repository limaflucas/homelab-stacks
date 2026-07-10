# Apps: Movie Request Agent (my-media-aigent)

This directory contains the Docker Compose configuration for the **Movie Request Agent** (`my-media-aigent`).

## Description

The Movie Request Agent is a Telegram bot that parses media links (IMDb, Letterboxd, TMDB, MyAnimeList, Netflix, etc.) sent by users, matches them against the Seerr/Overseerr API, and allows them to request media directly from Telegram.

## Architecture & Integration

*   **Registry**: The image is pulled from the local private registry: `registry.homelab/homelab/my-media-aigent:latest`.
*   **Networking**:
    *   `infra_internet`: Enables the bot to connect to the Telegram Bot API (`api.telegram.org`) and scrape external websites.
    *   `infra_media_internal`: Connects the agent directly to the Seerr service inside the media stack (`http://seerr:5055`).
*   **Secrets**: Leverages external Docker secrets for sensitive API credentials.

## Prerequisites

Before deploying, ensure you have created the following Docker Secrets:

1.  **Telegram Bot Token**:
    ```bash
    echo "YOUR_TELEGRAM_BOT_TOKEN" | docker secret create telegram_bot_token -
    ```
2.  **Seerr/Overseerr API Key**:
    ```bash
    echo "YOUR_SEERR_API_KEY" | docker secret create overseerr_api_key -
    ```

## Deploying the Stack

### Docker Swarm Mode (Recommended)

Deploy the service to your Swarm cluster:
```bash
docker stack deploy --with-registry-auth -c compose.yaml my-media-aigent
```

### Single Node Docker Compose Mode

If you are running in standard Docker Compose mode, ensure that the external networks (`infra_media_internal`, `infra_internet`) exist and secrets are configured. You can start the service with:
```bash
docker compose up -d
```

## Configuration Details

*   **Image**: `registry.homelab/homelab/my-media-aigent:latest`
*   **Timezone**: `America/Halifax`
*   **Overseerr URL**: `http://seerr:5055` (uses Swarm DNS resolution over the `infra_media_internal` overlay network).
*   **Resource Limits**: Limited to 0.5 CPU and 256MB memory.

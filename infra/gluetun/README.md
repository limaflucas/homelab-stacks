# Infrastructure: Gluetun

This directory contains the configuration for **Gluetun**, a lightweight Swiss-army-knife VPN client in a container, specifically configured for **NordVPN** over **WireGuard**.

## Architecture

- **Mode:** Docker Swarm Service
- **Role:** VPN Gateway / Proxy
- **Image:** `ghcr.io/qdm12/gluetun:v3`
- **Networking:** 
    - **Proxy Mode:** Provides HTTP and SOCKS5 proxies to the cluster via the `infra` overlay network.
    - **Internal Network:** Connected to `media-internal` for secure communication with media services.
- **Placement:** Restricted to a **manager node** for stable lifecycle management and access to the host's `/dev/net/tun` device.

## Features

- **Kill Switch:** Built-in firewall prevents traffic leaks if the VPN tunnel drops.
- **Proxy Support:** Enables other services to route traffic through the VPN using `gluetun:8888` (HTTP) or `gluetun:1080` (SOCKS5).
- **Secrets Management:** Sensitive credentials (Private Key) and filters (Countries) are managed via Docker Secrets.
- **Dynamic Updates:** Automatically downloads the latest `servers.json` from GitHub on every startup to ensure the server list is up-to-date.
- **Health Monitoring:** Built-in healthcheck monitors the VPN status on port `9999`.

## Installation Steps

### 1. Create External Secrets
Before deploying, create the secrets for your VPN configuration.

```bash
# Your Preferred VPN Countries (comma-separated, e.g., Switzerland,Netherlands)
echo "Switzerland,Netherlands" | docker secret create vpn_countries -

# Your NordVPN WireGuard Private Key
echo "your_private_key_here" | docker secret create vpn_private_key -
```

*Note: While `vpn_addresses` is defined in the compose file, it is not currently mounted to the service as it is not required for the standard NordVPN WireGuard setup.*

### 2. Deploy the Stack
Deploy Gluetun to the `infra` stack:
```bash
docker stack deploy -c compose.yaml infra
```

## Usage: Routing Other Services

Since Docker Swarm does not support `network_mode: container:gluetun`, other services must use Gluetun as a proxy.

### Example: Alpine Linux via Proxy
In another service's `compose.yaml`:
```yaml
services:
  myapp:
    image: alpine
    networks:
      - infra
    environment:
      - HTTP_PROXY=http://gluetun:8888
      - HTTPS_PROXY=http://gluetun:8888
    command: wget -qO- https://ifconfig.me
```

## Configuration Details

- **Persistence:** Config data and certificates are stored in `/mnt/docker-data/infra/gluetun`.
- **Ports:**
    - `8888`: HTTP Proxy
    - `1080`: SOCKS5 Proxy
    - `8388`: Shadowsocks (TCP/UDP)
- **Dynamic servers.json:** The entrypoint script uses `wget` to fetch the latest server list from the Gluetun GitHub repository before starting the VPN client.
- **Healthcheck:** Configured to check `http://127.0.0.1:9999/` every 90 seconds.
- **Logging:** `LOG_LEVEL` is set to `debug` for detailed troubleshooting.

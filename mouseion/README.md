# mouseion

Media automation. Downloads go through a NordVPN WireGuard tunnel.

| Service | URL | Notes |
| :--- | :--- | :--- |
| `seerr` | `https://catalog.homelab` | Requests, PostgreSQL |
| `radarr` | `https://movies.homelab` | Movies, PostgreSQL |
| `sonarr` | `https://tvshows.homelab` | TV and anime, PostgreSQL |
| `prowlarr` | `https://prowlarr.homelab` | Indexers, synced to Radarr and Sonarr |
| `sabnzbd` | `https://nzb.homelab` | Usenet; uses `gluetun` as its DNS server |
| `gluetun` | | VPN client; countries come from the `vpn_countries` secret |
| `gluetun-socks` | | SOCKS5 proxy (gost) into the VPN |

The databases are on 192.168.5.30. Media lives on the GlusterFS volume `pirateflix`, mounted at `/mnt/pirateflix`.

## Setup

Host directories:
*   `/mnt/docker-data/services/`: `gluetun` and `{prowlarr,radarr,sabnzbd,seerr,sonarr}/config`
*   `/mnt/pirateflix/`: `media/{movies,tv,animes}` and `downloads/{incomplete,complete}`

```bash
echo "<countries>" | docker secret create vpn_countries -
echo "<wireguard private key>" | docker secret create vpn_private_key -
echo "<password>" | docker secret create radarr_database_password -
echo "<password>" | docker secret create sonarr_database_password -
echo "<password>" | docker secret create seerr_db_password -
```

## Deploy and check

```bash
docker stack deploy -c compose.yaml mouseion
docker stack services mouseion
docker service logs mouseion_gluetun
```

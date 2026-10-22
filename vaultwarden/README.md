# vaultwarden

Bitwarden-compatible password manager at `https://vaultwarden.homelab`. Data is in PostgreSQL (192.168.5.30) and `/mnt/docker-data/services/vaultwarden`.

## Setup and deploy

```bash
echo "<db user>" | docker secret create vaultwarden_db_user -
echo "<db password>" | docker secret create vaultwarden_db_password -
docker stack deploy -c compose.yaml vaultwarden
```

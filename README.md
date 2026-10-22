# Homelab

Docker Swarm stacks for the homelab. Each directory is one stack, deployed under its own name.

The swarm runs on three Debian VMs, all managers: `vm-docker-zeus` (192.168.5.101), `vm-docker-adam` (.102) and `vm-docker-bragi` (.103). Service data lives on the GlusterFS volume `dockerdata`, mounted at `/mnt/docker-data` on every node.

| Stack | Services | Purpose |
| :--- | :--- | :--- |
| [`infra`](./infra/README.md) | traefik, authelia, registry, komodo, periphery, minio | Ingress, SSO, registry, Komodo, S3 |
| [`appflowy`](./appflowy/README.md) | appflowy-cloud, appflowy-web, appflowy-admin, gotrue, appflowy-redis | AppFlowy Cloud |
| [`devflow`](./devflow/README.md) | gitea, gitea-runner, plane, rabbitmq, valkey | Git, CI and Plane board |
| [`llms`](./llms/README.md) | litellm, open-webui | LLM gateway and chat |
| [`mouseion`](./mouseion/README.md) | radarr, sonarr, prowlarr, sabnzbd, seerr, gluetun, gluetun-socks | Media automation behind a VPN |
| [`my-media-aigent`](./my-media-aigent/README.md) | my-media-aigent, whisper | Telegram media bot |
| [`vaultwarden`](./vaultwarden/README.md) | vaultwarden | Password manager |

## Outside the swarm

| Service | Proxmox guest | Address |
| :--- | :--- | :--- |
| PostgreSQL 18 | CT 110 adam (primary), CT 111 bragi (standby) | 192.168.5.30, .31 |
| MongoDB 8.0 `rs0` | CT 120 adam, CT 121 zeus, CT 122 bragi | 192.168.5.40-42 |
| step-ca | CT 130 bragi (HA to adam or zeus) | `https://stepca.homelab` |
| pihole | CT 104 adam | `https://pihole.homelab/admin/` |
| Plex | CT 101 adam | `http://plex.homelab` |
| Ollama | CT 102 zeus | `zeus.ollama.homelab:11434` |
| Proxmox UI | all nodes, through Traefik | `https://proxmox.homelab` |

See [infra](./infra/README.md) for details.

## Deploy

From a stack's directory, after creating the secrets and directories its README lists:

```bash
docker stack deploy -c compose.yaml <stack>
```

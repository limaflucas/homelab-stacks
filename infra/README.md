# infra

| Service | Purpose |
| :--- | :--- |
| `traefik` | Reverse proxy for every `*.homelab` app, on ports 80, 443 and 8006 |
| `authelia` | SSO and OIDC, backed by PostgreSQL |
| `registry` | Private image registry `registry.homelab`, htpasswd auth |
| `komodo` | Komodo Core, backed by MongoDB `rs0` |
| `periphery` | Komodo agent, one per node |
| `minio` | S3 for AppFlowy and Plane. Runs `pgsty/minio` because `minio/minio` left Docker Hub |

The stack also declares the overlay networks the app stacks join (`*_private`, `minio_net`), so Traefik can reach them.

## Routing

Traefik reads routes from each service's `deploy.labels` and picks up changes within 15 seconds, without a restart. To publish a service, add these labels and a pihole CNAME `<name>.homelab` → `docker.homelab`:

```yaml
deploy:
  labels:
    - traefik.enable=true
    - traefik.swarm.network=<network shared with traefik>
    - traefik.http.routers.<name>.rule=Host(`<name>.homelab`)
    - traefik.http.services.<name>.loadbalancer.server.port=<port>
```

*   **TLS:** certificates come from step-ca over ACME (`https://stepca.homelab/acme/acme/directory`). They last 24 hours, hence `certificatesDuration=24`. `acme.json` lives in `/mnt/docker-data/services/traefik/data`, so Traefik runs one replica.
*   **HTTP:** `web` (:80) redirects to HTTPS at priority 1, so plain-HTTP routers like Plex still win.
*   **Uploads:** `readTimeout=0` keeps large uploads from being cut at 60 seconds.
*   **Headers:** `aliasHeadersStrategy=delete` drops headers like `X_Auth_User`, so Authelia's `Remote-*` headers can't be spoofed.
*   **Authelia:** add the middleware `authelia@swarm` to a router. It only works under `*.authelia.homelab`, the domain of Authelia's session cookie.
*   **Dashboard:** `https://traefik.authelia.homelab/dashboard/`.
*   **Routes outside the swarm** are files in [`traefik/dynamic/`](./traefik/dynamic/), copied to `/mnt/docker-data/services/traefik/dynamic/`:
    *   `plex.yml`: `http://plex.homelab`, HTTP only, because TVs don't trust the homelab CA.
    *   `proxmox.yml`: `https://proxmox.homelab` and `:8006`, spread across the three nodes with health checks and a sticky cookie.
    *   Traefik only notices a change written on the VM it runs on, because GlusterFS doesn't forward file events. Otherwise, run `docker service update --force infra_traefik`.

## Certificates (step-ca)

CT 130 `stepca` (192.168.5.50), built with the [community-scripts step-ca LXC](https://community-scripts.org/scripts/step-ca).

*   **Root:** `Homelab CA Root CA`, valid until 2036, SHA-256 `8E:0B:AB:AA:ED:6A:C6:99:D4:45:58:92:A4:75:9C:1E:0B:51:10:2C:C7:33:D7:76:32:0A:D3:0D:20:25:9C:A6`. Download it from `https://stepca.homelab/roots.pem`. Services mount it from `/mnt/docker-data/services/homelab-ca/root_ca.crt`.
*   **Files:** `/etc/step-ca`. `password.txt` unlocks the intermediate key. The root key is kept apart in `/root/ca-offline/root_ca_key`.
*   **Provisioners:**
    *   `acme`: 24 hours, for Traefik.
    *   `acme-hosts`: 90 days, for Proxmox and pihole.
    *   `Admin JWK`: administration.
*   **HA:** step-ca runs on bragi. If bragi goes down, HA restarts it on adam or zeus, then moves it back when bragi returns (rule `stepca-prefer-bragi`).
    *   Its disk is replicated to adam and zeus every 5 minutes (jobs `130-0` and `130-1`).
    *   While bragi is up, Proxmox refuses migrations to the other nodes. To test, disable the rule with `ha-manager rules set node-affinity stepca-prefer-bragi --disable 1`, then re-enable it with `--delete disable`.
*   **Proxmox:** each node renews its own `<node>.homelab` certificate (ACME account `stepca`, HTTP-01 on port 80).
*   **pihole (CT 104):** `pihole-tls-renew.timer` renews `pihole.homelab` and `pi.hole` when fewer than 30 days remain. `webserver.domain` is `pihole.homelab`. pihole has no admin password, so it answers 403 to other hostnames.

## Databases

Built with the community-scripts [PostgreSQL](https://community-scripts.org/scripts/postgresql) and [MongoDB](https://community-scripts.org/scripts/mongodb) LXCs.

*   **PostgreSQL 18:**
    *   Primary `postgresql-adam` (CT 110, `192.168.5.30:5432`) and hot standby `postgresql-bragi` (CT 111, `192.168.5.31`), through the slot `postgresql_bragi`.
    *   Apps connect to the primary. There is no automatic failover.
    *   Settings are in `/etc/postgresql/18/main/conf.d/90-homelab.conf` and `pg_hba.conf`.
*   **MongoDB 8.0 `rs0`:** `192.168.5.40` (CT 120 adam, primary), `.41` (CT 121 zeus) and `.42` (CT 122 bragi), with keyfile `/etc/mongodb/keyfile`. Used by Komodo.
*   **Admin credentials:** the swarm secrets `postgresql_superuser_password`, `mongodb_user` and `mongodb_password` hold them; no service mounts them. The replicator password is only in CT 111's `~postgres/.pgpass`.

## Setup

Host directories under `/mnt/docker-data/services/`:
*   `komodo/{keys,backups,repos}`
*   `periphery/<node>/{keys,repos}`. Periphery clones repos into `repos`, so they survive container restarts.
*   `homelab-ca/root_ca.crt`
*   `traefik/data/acme.json` (mode 600) and `traefik/dynamic`
*   `registry`
*   `authelia/config` (copy `authelia/*.yml` into it; hash user passwords with `authelia crypto hash generate`)
*   `minio/data`

Secrets:

```bash
printf '%s' "mongodb://komodo:<password>@192.168.5.40:27017,192.168.5.41:27017,192.168.5.42:27017/komodo?replicaSet=rs0&authSource=admin" | docker secret create komodo_db_uri_v2 -
openssl rand -base64 32 | tr -d '\n' | docker secret create komodo_jwt_secret -
openssl rand -base64 32 | tr -d '\n' | docker secret create komodo_webhook_secret -
echo "<oidc client secret>" | docker secret create komodo_oidc_client_secret -
echo "<onboarding key>" | docker secret create onboarding_vm-docker-adam -
echo "<onboarding key>" | docker secret create onboarding_vm-docker-zeus -
echo "<onboarding key>" | docker secret create onboarding_vm-docker-bragi -
openssl rand -base64 32 | docker secret create registry_http_secret -
cat registry.htpasswd | docker secret create registry_htpasswd -
openssl rand -base64 32 | docker secret create authelia_jwt_secret -
openssl rand -base64 32 | docker secret create authelia_session_secret -
openssl rand -base64 32 | docker secret create authelia_storage_encryption_key -
openssl rand -base64 32 | docker secret create authelia_oidc_hmac_secret -
echo "<authelia db password>" | docker secret create authelia_db_password -
echo "<minio root user>" | docker secret create minio_root_user -
echo "<minio root password>" | docker secret create minio_root_password -
```

## Checks

```bash
docker service logs infra_traefik 2>&1 | grep -E 'ERR|WRN'
docker exec $(docker ps -qf name=infra_authelia) authelia validate-config --config /config/configuration.yml
```

On adam:

```bash
pct exec 110 -- runuser -u postgres -- psql -c "SELECT application_name, state, replay_lag FROM pg_stat_replication;"
pct exec 120 -- mongosh -u <user> -p --authenticationDatabase admin --eval 'rs.status().members.map(m => m.name + " " + m.stateStr)'
```

On bragi:

```bash
ha-manager status | grep ct:130
pct exec 130 -- step ca health --ca-url https://stepca.homelab --root /etc/step-ca/certs/root_ca.crt
```

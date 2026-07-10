# Infrastructure: Step-CA

**Smallstep Certificate Authority** for the Homelab, optimized for Docker Swarm and internal PKI management.

## Architecture

- **Mode:** Docker Swarm Service
- **Role:** Internal Certificate Authority (Root/Intermediate)
- **Image:** `smallstep/step-ca:latest`
- **ACME:** Enabled by default for automated certificate issuance.
- **Remote Management:** Enabled for CLI-based configuration updates.
- **Network:** Connected to the `infra` overlay network.

## Installation Steps

### 1. Create External Secrets
Step-CA requires a password and an existing Root CA (or it will generate one, but this config assumes you are providing yours).

```bash
# 1. Create the CA password secret
echo "your-strong-password" | docker secret create step_ca_password -

# 2. Create secrets for your existing Root CA files (if applicable)
docker secret create step_ca_root_ca_key path/to/root_ca.key
docker secret create step_ca_root_ca_crt path/to/root_ca.crt
```

### 2. Deploy the Stack
Deploy Step-CA as part of your infrastructure:
```bash
docker stack deploy -c compose.yaml infra
```

## Initialization Details

The service is configured for automated initialization via environment variables:
- **Common Name:** `Homelab CA`
- **DNS Names:** `step-ca`, `stepca.homelab`, `localhost`
- **Provisioner:** `step-ca` (default)
- **ACME:** Enabled (`DOCKER_STEPCA_INIT_ACME=true`)
- **Remote Management:** Enabled (`DOCKER_STEPCA_INIT_REMOTE_MANAGEMENT=true`)

## Usage

### Get the Root CA Fingerprint
Needed to bootstrap other clients:
```bash
docker exec $(docker ps -q -f name=infra_step-ca) step certificate fingerprint /home/step/certs/root_ca.crt
```

### ACME Endpoint
Available within the `infra` network at:
`https://step-ca:9000/acme/acme/directory`

### Managed Provisioners
To add new provisioners (e.g., for OIDC or additional ACME endpoints):
1. Exec: `docker exec -it $(docker ps -q -f name=infra_step-ca) sh`
2. Command: `step ca provisioner add <name> --type <type>`
3. Reload: `kill -HUP 1`

## Configuration Details

- **Timezone:** `America/Halifax`
- **Persistence:** 
    - Certs: `/mnt/docker-data/infra/step-ca/certs` -> `/home/step/certs`
    - Config: `/mnt/docker-data/infra/step-ca/config` -> `/home/step/config`
    - DB: `/mnt/docker-data/infra/step-ca/db` -> `/home/step/db`
- **Resources:** 0.2 CPU / 128M Memory
- **Healthcheck:** Monitored via `step ca health` on port 9000.

## Secret Mapping

The `compose.yaml` uses specific target mapping for the `step-ca` container to bootstrap correctly:

| Secret Source | Target Path | Description |
| :--- | :--- | :--- |
| `step_ca_password` | `/run/secrets/step_ca_password` | Password for CA initialization |
| `step_ca_password` | `/run/secrets/root_ca_key_password` | Used to decrypt the Root CA Key |
| `step_ca_root_ca_key` | `/run/secrets/root_ca_key` | The Root CA private key |
| `step_ca_root_ca_crt` | `/run/secrets/root_ca.crt` | The Root CA certificate |

# Infrastructure: Step-CA

Smallstep Certificate Authority for the Homelab, optimized for Docker Swarm.

## Quick Start

1.  **Create the necessary Docker secrets:**
    Before deploying, you must create the Docker secrets for the CA:
    ```bash
    echo "your-strong-password" | docker secret create step_ca_password -
    docker secret create step_ca_root_ca_key path/to/root_ca.key
    docker secret create step_ca_root_ca_crt path/to/root_ca.crt
    ```

2.  **Deploy the service:**
    Step-CA is typically deployed as part of the `infra` stack:
    ```bash
    docker stack deploy -c compose.yaml infra
    ```

3.  **Initialize (Automated):**
    The service is configured to automatically initialize using root certificates provided via Docker secrets:
    - **Name:** Homelab CA
    - **Provisioner:** `step-ca`
    - **ACME:** Enabled by default (`DOCKER_STEPCA_INIT_ACME=true`)
    - **DNS Names:** `step-ca`, `stepca.homelab`, `localhost`

4.  **Get the Root CA Fingerprint:**
    You will need the fingerprint to bootstrap other services.
    ```bash
    docker exec $(docker ps -q -f name=infra_step-ca) step certificate fingerprint /home/step/certs/root_ca.crt
    ```

5.  **Copy the Root Certificate:**
    To use the CA in other services, you may need to provide the `root_ca.crt`:
    ```bash
    cat /mnt/docker-data/infra/step-ca/certs/root_ca.crt
    ```

## ACME Endpoint

Since ACME is initialized automatically, the endpoint is immediately available at:
`https://step-ca:9000/acme/acme/directory`

To add *additional* ACME provisioners or manage existing ones:
1.  **Exec into the container:**
    ```bash
    docker exec -it $(docker ps -q -f name=infra_step-ca) sh
    ```
2.  **Add a new provisioner (example):**
    ```bash
    step ca provisioner add my-new-acme --type ACME
    ```
3.  **Signal the CA to reload:**
    ```bash
    kill -HUP 1
    ```

## Configuration Details

- **Timezone:** `America/Halifax`
- **Remote Management:** Enabled (`DOCKER_STEPCA_INIT_REMOTE_MANAGEMENT=true`)
- **Persistence:** Data is stored in:
    - Certs: `/mnt/docker-data/infra/step-ca/certs`
    - Database: `/mnt/docker-data/infra/step-ca/db`
    - Config: `/mnt/docker-data/infra/step-ca/config`
- **Network:** Connected to the `infra` overlay network.
- **Healthcheck:** Enabled to monitor CA availability via `step ca health`.
- **Resources:** Limited to 0.2 CPU and 128M RAM.

## Security (Docker Secrets)

The CA uses external Docker secrets for sensitive files:
- `step_ca_password`: The password for the root CA key.
- `step_ca_root_ca_key`: The root CA private key.
- `step_ca_root_ca_crt`: The root CA certificate.

*(Note: These secrets must exist before the stack is deployed.)*

# Step-CA

Smallstep Certificate Authority for the Homelab.

## Quick Start

1.  **Create the CA password secret:**
    Before deploying, you must create the Docker secret for the CA password:
    ```bash
    echo "your-strong-password" | docker secret create step_ca_password -
    ```

2.  **Deploy the service:**
    ```bash
    docker stack deploy -c compose.yaml infra
    ```

3.  **Initialize (Automated):**
    The service is configured to automatically initialize with:
    - **Name:** Homelab CA
    - **Provisioner:** `stepca`
    - **ACME:** Enabled by default (`DOCKER_STEPCA_INIT_ACME=true`)
    - **DNS Names:** `localhost`, `stepca.homelab`

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
`https://stepca.homelab:9000/acme/acme/directory`

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
- **Persistence:** Data is stored in `/mnt/docker-data/infra/step-ca`.
- **Network:** Uses the stack's default overlay network.
- **Resources:** Limited to 0.2 CPU and 128M RAM.

## Security (Docker Secrets)

The CA password is managed via the `step_ca_password` external secret. If you need to rotate the password:
1. Remove the service.
2. Update/recreate the secret.
3. Redeploy the service.
*(Note: Changing the password after initialization requires manual updates to the encrypted keys in the volume.)*

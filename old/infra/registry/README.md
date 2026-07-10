# Infrastructure: Docker Registry

A private **Docker Registry** service for hosting container images locally within the homelab, optimized for Docker Swarm.

## Architecture

- **Mode:** Docker Swarm Service
- **Role:** Local Container Registry
- **Image:** `registry:2`
- **Persistence:**
    - Data: `/mnt/docker-data/infra/registry` -> `/var/lib/registry`
- **Network:** Connected to the `internet` overlay network (which resolves to `infra_internet` for other stacks in the swarm).
- **Placement:** Restricted to a manager/non-bragi node for stable persistence.
- **Resource Limits:** 0.5 CPU / 512M Memory

## Installation Steps

### 1. Create the HTTP Secret
The registry uses an HTTP secret to sign state/session information. Generate and create this Docker Secret:

```bash
openssl rand -base64 32 | tr -d '\n' | docker secret create registry_http_secret -
```

### 2. Create the Htpasswd Authentication Secret
The registry requires basic authentication by default. 

Generate the `htpasswd` file locally (replacing `<username>` and `<password>` with your credentials) and load it into a Docker Secret:

```bash
# Generate the htpasswd content and create the secret
docker run --entrypoint htpasswd httpd:alpine -Bbn <username> <password> | docker secret create registry_htpasswd -
```

### 3. Deploy the Stack
Deploy the registry service as part of the `infra` stack:

```bash
docker stack deploy -c compose.yaml infra
```

## Reverse Proxy & SSL Setup

To securely access the registry from outside the overlay network (e.g., from development machines or other Docker hosts), configure a proxy host in **Nginx Proxy Manager**:

1. Log into your NPM admin dashboard (`http://<manager-ip>:81`).
2. Add a new **Proxy Host**:
   - **Domain Name:** `registry.homelab`
   - **Scheme:** `http`
   - **Forward Name/IP:** `registry`
   - **Forward Port:** `5000`
   - **Block Common Exploits:** Enabled
   - **Websockets Support:** Enabled (optional but recommended for docker push/pull APIs)
3. Under the **SSL** tab:
   - Select your Homelab certificate (generated via Step-CA).
   - Enable **Force SSL**.

## Client Authentication

Once deployed and proxied, log in from your Docker client:

```bash
docker login registry.homelab
```

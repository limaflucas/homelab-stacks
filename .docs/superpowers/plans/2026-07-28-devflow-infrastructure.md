# DevFlow Infrastructure Implementation Plan (Phases 0–1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that Claude Code can route through LiteLLM, then deploy the Plane board, Gitea, and CI runner stacks that the agentic workflow depends on — leaving a working kanban board and self-hosted Git even if no agent code is ever written.

**Architecture:** A single new Docker Swarm stack, `devflow`, containing Gitea, its `act_runner`, Plane (via the all-in-one community image), and Plane's two required backing services (Valkey and RabbitMQ). Postgres comes from the existing `pgpool` cluster and object storage from the existing MinIO — no new database infrastructure. Ingress is via the existing Nginx Proxy Manager over a new `devflow_private` overlay network.

**Tech Stack:** Docker Swarm, Gitea + `act_runner`, Plane AIO (community), Valkey, RabbitMQ, PostgreSQL 17 via Pgpool-II, MinIO, LiteLLM.

**Source spec:** `docs/superpowers/specs/2026-07-27-agentic-kanban-workflow-design.md`

## Global Constraints

- All stacks are Docker Swarm, deployed with `docker stack deploy -c compose.yaml <name>`.
- Timezone on every service: `TZ=America/Halifax`.
- Secrets are **external Docker Swarm secrets**, created with `docker secret create`. Never inline a credential in `compose.yaml`. `.gitignore` already excludes `**/secrets/`, `**/.env`, `**/*.env`.
- Persistent host paths live under `/mnt/docker-data/services/<service>/`.
- Every service declares `deploy.resources.limits` and `deploy.restart_policy`.
- Database access is via the `pgpool` external network at host `pgpool`, port `5432`.
- Each stack gets a `<stack>_private` external overlay network that NPM joins for ingress.
- New stacks get a `README.md` following the pattern of `llms/README.md`.
- Swarm manager commands run on a manager node (`vm-docker-zeus` is the local context).
- The `devflow` stack name is fixed; all service DNS names below assume it.

---

### Task 1: Phase 0 — Prove Claude Code routes through LiteLLM

This is a **gate**. Every later task assumes it, and the spec names it the least certain assumption. Do not proceed to Task 2 until this passes or the fallback is recorded.

**Files:**
- Create: `llms/docs/claude-code-passthrough-spike.md`

**Interfaces:**
- Consumes: nothing.
- Produces: a documented verdict — either `ANTHROPIC_BASE_URL=http://litellm:4000/anthropic` works, or the fallback (direct Anthropic API, budget enforced in Anthropic's console) is adopted. Task 9 depends on this verdict.

- [ ] **Step 1: Add an Anthropic-backed model to LiteLLM**

Add an Anthropic API key as a swarm secret and register a model. On a manager node:

```bash
printf '%s' 'sk-ant-REPLACE_WITH_REAL_KEY' | docker secret create anthropic_api_key -
```

Then add to `llms/compose.yaml` under the `litellm` service:

```yaml
    environment:
      - ANTHROPIC_API_KEY_FILE=/run/secrets/anthropic_api_key
    secrets:
      - anthropic_api_key
```

and at the file's bottom-level `secrets:` block:

```yaml
secrets:
  anthropic_api_key:
    external: true
```

- [ ] **Step 2: Register the model in LiteLLM and redeploy**

Add to `llms/config/litellm-config.yaml`, above `general_settings`:

```yaml
model_list:
  - model_name: claude-sonnet-5
    litellm_params:
      model: anthropic/claude-sonnet-5
      api_key: os.environ/ANTHROPIC_API_KEY
```

Copy the config to the host path the service mounts, then redeploy:

```bash
cp ./config/litellm-config.yaml /mnt/docker-data/services/litellm/config.yaml
docker stack deploy -c llms/compose.yaml llms
docker service logs llms_litellm --tail 50
```

Expected: no startup errors, and the model appears in the next step.

- [ ] **Step 3: Verify the OpenAI-compatible route works first**

Run from a host that can reach the `llms_private` network (or `docker exec` into the container):

```bash
curl -s http://litellm:4000/v1/models \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.data[].id'
```

Expected: `claude-sonnet-5` is listed alongside the local Ollama models.

- [ ] **Step 4: Verify the Anthropic-format passthrough route — the actual spike**

```bash
curl -s http://litellm:4000/anthropic/v1/messages \
  -H "x-api-key: $LITELLM_MASTER_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-sonnet-5","max_tokens":32,
       "messages":[{"role":"user","content":"Reply with the single word: OK"}]}' | jq .
```

Expected: a JSON response with `"type": "message"` and content containing `OK`.
If this returns 404 or an unrecognized-route error, the passthrough is unavailable — record that and go to Step 6.

- [ ] **Step 5: Verify Claude Code itself honors the base URL**

```bash
ANTHROPIC_BASE_URL=http://litellm:4000/anthropic \
ANTHROPIC_AUTH_TOKEN="$LITELLM_MASTER_KEY" \
claude -p "Reply with the single word: OK" --model claude-sonnet-5
```

Expected: `OK`. Then confirm the call was actually metered by LiteLLM:

```bash
curl -s http://litellm:4000/spend/logs \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.[-1] | {model, spend}'
```

Expected: a log entry for `claude-sonnet-5` with non-zero spend. **A response without a spend log means traffic bypassed the proxy — treat that as a failure of this spike.**

- [ ] **Step 6: Record the verdict**

Write `llms/docs/claude-code-passthrough-spike.md` containing: the date, the exact commands run, the observed output of Steps 4 and 5, and one of these two verdicts:

- **PASS** — agent runners set `ANTHROPIC_BASE_URL` to the LiteLLM passthrough; budget enforcement is LiteLLM's virtual key (Task 9 proceeds as written).
- **FAIL** — agent runners call `api.anthropic.com` directly with a dedicated Anthropic API key; budget enforcement moves to a spend limit configured in the Anthropic console. Task 9 is replaced by "configure a $50 monthly spend limit on the agent's Anthropic API key" and the Conductor loses the ability to detect budget exhaustion from an API error, so it must instead poll the Anthropic usage endpoint.

- [ ] **Step 7: Commit**

```bash
git add llms/compose.yaml llms/config/litellm-config.yaml llms/docs/claude-code-passthrough-spike.md
git commit -m "feat(llms): add Anthropic model to LiteLLM and record Claude Code passthrough spike"
```

---

### Task 2: Provision databases, MinIO bucket, and secrets

**Files:**
- Create: `devflow/README.md` (initial "Prerequisites" section only; later tasks extend it)

**Interfaces:**
- Consumes: the running `infra` stack (pgpool, MinIO).
- Produces: databases `gitea` and `plane`; DB users `gitea` and `plane`; MinIO bucket `plane-app` with an access key pair; the swarm secrets `gitea_db_password`, `plane_db_url`, `plane_secret_key`, `plane_minio_access_key`, `plane_minio_secret_key`, `rabbitmq_password`. All later tasks reference these exact names.

- [ ] **Step 1: Verify the databases do not yet exist**

```bash
docker exec -i $(docker ps -qf name=infra_pgsql-primary) \
  psql -U postgres -c "\l" | grep -E 'gitea|plane'
```

Expected: no output (neither database exists). If they do exist, stop and reconcile before continuing.

- [ ] **Step 2: Create the databases and roles**

Choose two strong passwords and keep them for Step 4. Run:

```bash
docker exec -i $(docker ps -qf name=infra_pgsql-primary) psql -U postgres <<'SQL'
CREATE DATABASE gitea;
CREATE USER gitea WITH PASSWORD 'REPLACE_GITEA_DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE gitea TO gitea;
ALTER DATABASE gitea OWNER TO gitea;

CREATE DATABASE plane;
CREATE USER plane WITH PASSWORD 'REPLACE_PLANE_DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE plane TO plane;
ALTER DATABASE plane OWNER TO plane;
SQL
```

`ALTER DATABASE ... OWNER TO` matters: both applications run schema migrations and need to create tables, extensions, and indexes.

- [ ] **Step 3: Verify the databases exist and the roles can connect**

```bash
docker exec -i $(docker ps -qf name=infra_pgsql-primary) \
  psql -U postgres -c "\l" | grep -E 'gitea|plane'
```

Expected: both databases listed, owned by their respective roles.

- [ ] **Step 4: Create the MinIO bucket and access key**

Open the MinIO console (via NPM), then:
1. Create a bucket named `plane-app`.
2. Set its access policy to **private**.
3. Create an access key pair scoped to that bucket. Record both halves.

- [ ] **Step 5: Create all swarm secrets**

On a manager node. Substitute the real values chosen above:

```bash
printf '%s' 'REPLACE_GITEA_DB_PASSWORD' | docker secret create gitea_db_password -
printf '%s' 'postgresql://plane:REPLACE_PLANE_DB_PASSWORD@pgpool:5432/plane' | docker secret create plane_db_url -
printf '%s' "$(openssl rand -hex 32)" | docker secret create plane_secret_key -
printf '%s' 'REPLACE_MINIO_ACCESS_KEY' | docker secret create plane_minio_access_key -
printf '%s' 'REPLACE_MINIO_SECRET_KEY' | docker secret create plane_minio_secret_key -
printf '%s' "$(openssl rand -hex 24)" | docker secret create rabbitmq_password -
```

Note `printf '%s'` rather than `echo` — a trailing newline in a secret is a real and painful source of authentication failures.

- [ ] **Step 6: Verify all six secrets exist**

```bash
docker secret ls --format '{{.Name}}' | grep -E 'gitea_db_password|plane_db_url|plane_secret_key|plane_minio_access_key|plane_minio_secret_key|rabbitmq_password' | sort
```

Expected: exactly six lines.

- [ ] **Step 7: Write the prerequisites README and commit**

Create `devflow/README.md` with a `# DevFlow Stack` heading and a `## Prerequisites` section documenting: the two databases and roles, the `plane-app` MinIO bucket, and the six secret names with what each holds (never the values). Later tasks append their own sections, including host directories.

```bash
git add devflow/README.md
git commit -m "docs(devflow): document database, bucket, and secret prerequisites"
```

---

### Task 3: Create the `devflow_private` network and wire NPM to it

NPM can only proxy to a service if it shares a network with it. This must land before any `devflow` service is reachable.

**Files:**
- Modify: `infra/compose.yaml` — the `npm` service's `networks:` list, and the top-level `networks:` block

**Interfaces:**
- Consumes: the running `infra` stack.
- Produces: an attachable overlay network named `devflow_private` that NPM is attached to. Tasks 4 and 6 attach their services to it.

- [ ] **Step 1: Add the network to the top-level `networks:` block**

In `infra/compose.yaml`, alongside the existing `llms_private` entry:

```yaml
  devflow_private:
    driver: overlay
    name: devflow_private
    attachable: true
```

- [ ] **Step 2: Attach NPM to it**

In the `npm` service's `networks:` mapping, after `llms_private:`, add:

```yaml
      devflow_private:
```

- [ ] **Step 3: Redeploy the infra stack**

```bash
docker stack deploy -c infra/compose.yaml infra
```

- [ ] **Step 4: Verify the network exists and NPM is attached**

```bash
docker network ls --filter name=devflow_private
docker service inspect infra_npm \
  --format '{{range .Spec.TaskTemplate.Networks}}{{.Target}} {{end}}' \
  | tr ' ' '\n' | xargs -I{} docker network inspect {} --format '{{.Name}}' 2>/dev/null | sort
```

Expected: `devflow_private` appears in both outputs. Confirm NPM came back healthy:

```bash
docker service ps infra_npm --no-trunc | head -5
```

Expected: the current task is `Running`, not `Failed`.

- [ ] **Step 5: Commit**

```bash
git add infra/compose.yaml
git commit -m "feat(infra): add devflow_private overlay network and attach NPM"
```

---

### Task 4: Deploy Gitea

**Files:**
- Create: `devflow/compose.yaml`
- Modify: `devflow/README.md`

**Interfaces:**
- Consumes: `gitea_db_password` secret, `pgpool` network, `devflow_private` network.
- Produces: Gitea reachable at `gitea:3000` on `devflow_private` and at `https://gitea.homelab` via NPM; SSH on host port `2222`. Task 5 registers a runner against it.

- [ ] **Step 1: Create the host directory**

```bash
sudo mkdir -p /mnt/docker-data/services/gitea/data
sudo chown -R 1000:1000 /mnt/docker-data/services/gitea
```

Gitea's container runs as uid/gid 1000; a wrong owner here produces a permission error on first boot rather than a clear message.

- [ ] **Step 2: Write `devflow/compose.yaml` with the Gitea service**

```yaml
services:
  #############################################
  # GITEA
  #############################################
  # SUPERSEDED — deployed as the *non-rootless* `gitea/gitea:1`. That image
  # serves SSH from an integrated OpenSSH daemon on container port 22, not from
  # Gitea's built-in Go server, so `SSH_LISTEN_PORT` is inert here and the
  # publish below must be "2222:22". Following this block as written produces a
  # connection that is refused (nothing published) or reset (published to the
  # wrong container port). See devflow/README.md.
  gitea:
    image: gitea/gitea:1-rootless
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        export GITEA__database__PASSWD=$$(cat /run/secrets/gitea_db_password)
        exec /usr/bin/entrypoint
    environment:
      - TZ=America/Halifax
      - GITEA__database__DB_TYPE=postgres
      - GITEA__database__HOST=pgpool:5432
      - GITEA__database__NAME=gitea
      - GITEA__database__USER=gitea
      - GITEA__server__DOMAIN=gitea.homelab
      - GITEA__server__ROOT_URL=https://gitea.homelab/
      - GITEA__server__SSH_DOMAIN=gitea.homelab
      - GITEA__server__SSH_PORT=2222
      - GITEA__service__DISABLE_REGISTRATION=true
      - GITEA__actions__ENABLED=true
    ports:
      - "2222:2222"
    volumes:
      - /mnt/docker-data/services/gitea/data:/var/lib/gitea
    secrets:
      - gitea_db_password
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/healthz"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.hostname != vm-docker-bragi
      resources:
        limits:
          cpus: '1'
          memory: 1G
      restart_policy:
        condition: on-failure
        delay: 10s
        max_attempts: 5
        window: 120s
    networks:
      - devflow_private
      - pgpool

networks:
  devflow_private:
    external: true
    name: devflow_private
  pgpool:
    external: true
    name: pgpool_net

secrets:
  gitea_db_password:
    external: true
```

- [ ] **Step 3: Deploy and watch it converge**

```bash
docker stack deploy -c devflow/compose.yaml devflow
docker service logs -f devflow_gitea
```

Expected: migration output followed by a listening message. `Ctrl-C` once it is serving.

- [ ] **Step 4: Verify health from inside the network**

```bash
docker run --rm --network devflow_private curlimages/curl:latest \
  -sf http://gitea:3000/api/healthz
```

Expected: JSON with `"status": "pass"`. A non-zero exit means the service is not serving — check `docker service ps devflow_gitea --no-trunc`.

- [ ] **Step 5: Create the NPM proxy host and the admin user**

In NPM, add a proxy host: domain `gitea.homelab`, forward to `gitea` port `3000`, request a cert from the internal step-ca ACME provider, and enable websocket support (Gitea Actions log streaming needs it).

Then open `https://gitea.homelab` and complete the installer, creating the admin account. Registration is disabled, so this first account is the only one until you invite more.

- [ ] **Step 6: Verify the API responds as the admin user**

Create a personal access token in Gitea (`Settings → Applications`) with `repo` and `write:repository` scopes, then:

```bash
curl -sf -H "Authorization: token $GITEA_TOKEN" https://gitea.homelab/api/v1/user | jq '.login'
```

Expected: your admin username. Keep `$GITEA_TOKEN` — Task 5 uses it.

- [ ] **Step 7: Document and commit**

Add a `## Gitea` section to `devflow/README.md` covering the host directory, the `2222` SSH port mapping, and the NPM proxy host settings.

```bash
git add devflow/compose.yaml devflow/README.md
git commit -m "feat(devflow): add Gitea service backed by pgpool"
```

---

### Task 5: Deploy the Gitea Actions runner

**Files:**
- Modify: `devflow/compose.yaml`, `devflow/README.md`
- Create: a throwaway test repository in Gitea (not in this repo)

**Interfaces:**
- Consumes: running Gitea from Task 4, `$GITEA_TOKEN`.
- Produces: a registered `act_runner` labelled `homelab` that executes workflows. The monorepo's CI (a later plan) depends on this label existing.

> **Reconciled 2026-07-30.** This step's end state is correct — one runner
> labelled `homelab` — but the route there was not direct. Implementation first
> split into three runners (`homelab-api` / `-web` / `-mobile`), because a
> runner's label→image mapping is fixed at registration, so three job images
> meant three services. Once workflows began naming their own image via
> `jobs.<id>.container.image` (which act_runner honours ahead of the label
> default), that mapping had nothing left to do and the three collapsed back to
> one at `capacity: 5`. The label's image is now only a fallback, and nothing
> project-specific lives in this repo. Do not re-derive the split: it buys
> nothing once workflows choose their own images.

- [ ] **Step 1: Obtain a runner registration token**

```bash
curl -sf -X POST -H "Authorization: token $GITEA_TOKEN" \
  https://gitea.homelab/api/v1/admin/runners/registration-token | jq -r '.token'
```

Expected: an opaque token string. Store it as a secret:

```bash
printf '%s' 'PASTE_RUNNER_TOKEN' | docker secret create gitea_runner_token -
```

- [ ] **Step 2: Create the runner host directory**

```bash
sudo mkdir -p /mnt/docker-data/services/gitea-runner/data
```

- [ ] **Step 3: Add the runner service to `devflow/compose.yaml`**

Insert before the `networks:` block:

```yaml
  #############################################
  # GITEA ACTIONS RUNNER
  #############################################
  gitea-runner:
    image: gitea/act_runner:latest
    environment:
      - TZ=America/Halifax
      - GITEA_INSTANCE_URL=http://gitea:3000
      - GITEA_RUNNER_NAME=homelab-runner
      - GITEA_RUNNER_LABELS=homelab:docker://node:22-bookworm
      - CONFIG_FILE=/data/config.yaml
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        export GITEA_RUNNER_REGISTRATION_TOKEN=$$(cat /run/secrets/gitea_runner_token)
        exec /sbin/tini -- /opt/act/run.sh
    volumes:
      - /mnt/docker-data/services/gitea-runner/data:/data
      - /var/run/docker.sock:/var/run/docker.sock
    secrets:
      - gitea_runner_token
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.hostname != vm-docker-bragi
      resources:
        limits:
          cpus: '2'
          memory: 2G
      restart_policy:
        condition: on-failure
        delay: 15s
        max_attempts: 5
        window: 120s
    networks:
      - devflow_private
```

The runner mounts the Docker socket because it launches job containers as siblings. This grants it root-equivalent access to its node — acceptable here because it runs your own code on your own hardware, but it is the reason the runner is pinned off `vm-docker-bragi` and why Gitea registration is disabled.

Add to the `secrets:` block:

```yaml
  gitea_runner_token:
    external: true
```

- [ ] **Step 4: Deploy and verify registration**

```bash
docker stack deploy -c devflow/compose.yaml devflow
docker service logs -f devflow_gitea-runner
```

Expected: a line reporting successful registration, then `Runner: homelab-runner ... listening`.

Confirm from Gitea's side:

```bash
curl -sf -H "Authorization: token $GITEA_TOKEN" \
  https://gitea.homelab/api/v1/admin/runners | jq '.[] | {name, status, labels}'
```

Expected: `homelab-runner` with status `online` and the `homelab` label.

- [ ] **Step 5: Prove a workflow actually executes**

In Gitea, create a repository named `ci-smoke-test`. Add `.gitea/workflows/smoke.yaml`:

```yaml
name: smoke
on: [push]
jobs:
  hello:
    runs-on: homelab
    steps:
      - run: echo "runner is alive"
      - run: node --version
```

Push it. Then check the run:

```bash
curl -sf -H "Authorization: token $GITEA_TOKEN" \
  "https://gitea.homelab/api/v1/repos/$GITEA_USER/ci-smoke-test/actions/runs" \
  | jq '.workflow_runs[0] | {status, conclusion}'
```

Expected: `status: "completed"`, `conclusion: "success"`. **This is the real test — a registered runner that never executes a job is a common and silent failure mode.** If the job stays queued, the label in `runs-on` does not match `GITEA_RUNNER_LABELS`.

- [ ] **Step 6: Document and commit**

Add a `## Gitea Actions Runner` section to `devflow/README.md` noting the `homelab` label, the Docker socket mount and its security implication, and how to re-issue a registration token.

```bash
git add devflow/compose.yaml devflow/README.md
git commit -m "feat(devflow): add Gitea Actions runner with homelab label"
```

---

### Task 6: Deploy Plane and its backing services

Plane needs Redis and RabbitMQ in addition to Postgres and S3. The all-in-one community image collapses Plane's own ~8 services into one container, which is what makes this tractable on Swarm.

**Files:**
- Modify: `devflow/compose.yaml`, `devflow/README.md`

**Interfaces:**
- Consumes: `plane_db_url`, `plane_secret_key`, `plane_minio_access_key`, `plane_minio_secret_key`, `rabbitmq_password` secrets; the `plane-app` MinIO bucket.
- Produces: Plane at `https://plane.homelab`. Task 7 configures its board; Task 8 exercises its API.

- [ ] **Step 1: Create host directories**

```bash
sudo mkdir -p /mnt/docker-data/services/plane-valkey/data
sudo mkdir -p /mnt/docker-data/services/plane-rabbitmq/data
```

- [ ] **Step 2: Add Valkey and RabbitMQ to `devflow/compose.yaml`**

Insert before the `networks:` block:

```yaml
  #############################################
  # PLANE — VALKEY (Redis)
  #############################################
  plane-valkey:
    image: valkey/valkey:8-alpine
    command: ["valkey-server", "--save", "60", "1", "--appendonly", "no"]
    environment:
      - TZ=America/Halifax
    volumes:
      - /mnt/docker-data/services/plane-valkey/data:/data
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 15s
      timeout: 5s
      retries: 5
    deploy:
      mode: replicated
      replicas: 1
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
      restart_policy:
        condition: on-failure
        delay: 10s
        max_attempts: 5
        window: 120s
    networks:
      - devflow_private

  #############################################
  # PLANE — RABBITMQ
  #############################################
  plane-rabbitmq:
    image: rabbitmq:4-alpine
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        export RABBITMQ_DEFAULT_PASS=$$(cat /run/secrets/rabbitmq_password)
        exec docker-entrypoint.sh rabbitmq-server
    environment:
      - TZ=America/Halifax
      - RABBITMQ_DEFAULT_USER=plane
      - RABBITMQ_DEFAULT_VHOST=plane
    volumes:
      - /mnt/docker-data/services/plane-rabbitmq/data:/var/lib/rabbitmq
    secrets:
      - rabbitmq_password
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    deploy:
      mode: replicated
      replicas: 1
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
      restart_policy:
        condition: on-failure
        delay: 10s
        max_attempts: 5
        window: 120s
    networks:
      - devflow_private
```

- [ ] **Step 3: Verify the two backing services before adding Plane**

Deploy and check each independently — Plane failing to start is much harder to diagnose than Valkey failing to start.

```bash
docker stack deploy -c devflow/compose.yaml devflow
docker run --rm --network devflow_private valkey/valkey:8-alpine valkey-cli -h plane-valkey ping
```

Expected: `PONG`.

```bash
docker service ps devflow_plane-rabbitmq --no-trunc | head -3
```

Expected: current task `Running`. Confirm the vhost exists:

```bash
docker exec -i $(docker ps -qf name=devflow_plane-rabbitmq) rabbitmqctl list_vhosts
```

Expected: `plane` is listed.

- [ ] **Step 4: Add the Plane AIO service**

Insert before the `networks:` block:

```yaml
  #############################################
  # PLANE (all-in-one, community)
  #############################################
  plane:
    image: makeplane/plane-aio-community:latest
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        export DATABASE_URL=$$(cat /run/secrets/plane_db_url)
        export SECRET_KEY=$$(cat /run/secrets/plane_secret_key)
        export AWS_ACCESS_KEY_ID=$$(cat /run/secrets/plane_minio_access_key)
        export AWS_SECRET_ACCESS_KEY=$$(cat /run/secrets/plane_minio_secret_key)
        export AMQP_URL=amqp://plane:$$(cat /run/secrets/rabbitmq_password)@plane-rabbitmq:5672/plane
        exec /app/start.sh
    environment:
      - TZ=America/Halifax
      - DOMAIN_NAME=plane.homelab
      - WEB_URL=https://plane.homelab
      - REDIS_URL=redis://plane-valkey:6379
      - AWS_REGION=us-east-1
      - AWS_S3_BUCKET_NAME=plane-app
      - AWS_S3_ENDPOINT_URL=http://minio:9000
      - FILE_SIZE_LIMIT=10485760
      - CORS_ALLOWED_ORIGINS=https://plane.homelab
    secrets:
      - plane_db_url
      - plane_secret_key
      - plane_minio_access_key
      - plane_minio_secret_key
      - rabbitmq_password
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/"]
      interval: 30s
      timeout: 10s
      retries: 10
      start_period: 180s
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.hostname != vm-docker-bragi
      resources:
        limits:
          cpus: '2'
          memory: 4G
      restart_policy:
        condition: on-failure
        delay: 20s
        max_attempts: 5
        window: 300s
    networks:
      - devflow_private
      - pgpool
      - minio
```

Add to the top-level `networks:` block:

```yaml
  minio:
    external: true
    name: minio_net
```

Add to the `secrets:` block:

```yaml
  plane_db_url:
    external: true
  plane_secret_key:
    external: true
  plane_minio_access_key:
    external: true
  plane_minio_secret_key:
    external: true
  rabbitmq_password:
    external: true
```

The `start_period: 180s` is deliberate: the AIO image runs Django migrations against an empty database on first boot, and a shorter grace period will restart-loop the container mid-migration.

- [ ] **Step 5: Deploy and watch migrations complete**

```bash
docker stack deploy -c devflow/compose.yaml devflow
docker service logs -f devflow_plane
```

Expected: Django migration output, then worker and web-server startup. This takes several minutes on first boot. Do not interrupt it.

- [ ] **Step 6: Verify Plane is serving**

```bash
docker run --rm --network devflow_private curlimages/curl:latest -sf -o /dev/null -w '%{http_code}\n' http://plane/
```

Expected: `200`.

Confirm the migrations actually created the schema:

```bash
docker exec -i $(docker ps -qf name=infra_pgsql-primary) \
  psql -U postgres -d plane -c "\dt" | head -10
```

Expected: a list of Plane tables, not "Did not find any relations."

- [ ] **Step 7: Add the NPM proxy host and create the first user**

In NPM: domain `plane.homelab`, forward to `plane` port `80`, internal ACME cert, websocket support enabled (Plane's live collaboration requires it).

Open `https://plane.homelab`, complete the setup wizard, and create the admin account and a workspace.

- [ ] **Step 8: Document and commit**

Add a `## Plane` section to `devflow/README.md` covering the three backing dependencies, the long first-boot migration, the MinIO bucket name, and the NPM settings.

```bash
git add devflow/compose.yaml devflow/README.md
git commit -m "feat(devflow): add Plane AIO with Valkey and RabbitMQ backing services"
```

---

### Task 7: Create the project and the eleven board states

**Files:**
- Create: `devflow/scripts/bootstrap-plane-board.sh`
- Modify: `devflow/README.md`

**Interfaces:**
- Consumes: running Plane, a Plane API token, a workspace slug.
- Produces: a Plane project whose states exactly match the spec's board topology. The Conductor (a later plan) matches on these exact state names.

- [ ] **Step 1: Create an API token and capture identifiers**

In Plane: `Workspace Settings → API Tokens → Add token`. Export what the script needs:

```bash
export PLANE_URL=https://plane.homelab
export PLANE_TOKEN=plane_api_...
export PLANE_WORKSPACE=your-workspace-slug
```

Verify the token works before writing anything:

```bash
curl -sf -H "X-API-Key: $PLANE_TOKEN" \
  "$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/" | jq '.results | length'
```

Expected: a number (`0` if you have not created a project yet). A 401 means the token or header name is wrong.

- [ ] **Step 2: Create the project**

```bash
curl -sf -X POST -H "X-API-Key: $PLANE_TOKEN" -H "Content-Type: application/json" \
  "$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/" \
  -d '{"name":"DevFlow","identifier":"DEV"}' | jq -r '.id'
```

Expected: a UUID. Export it: `export PLANE_PROJECT=<uuid>`.

- [ ] **Step 3: Write the bootstrap script**

Create `devflow/scripts/bootstrap-plane-board.sh`:

```bash
#!/usr/bin/env bash
# Creates the DevFlow board states in a Plane project.
# Requires: PLANE_URL, PLANE_TOKEN, PLANE_WORKSPACE, PLANE_PROJECT
set -euo pipefail

: "${PLANE_URL:?}" "${PLANE_TOKEN:?}" "${PLANE_WORKSPACE:?}" "${PLANE_PROJECT:?}"

API="$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/$PLANE_PROJECT/states/"

# name | group | colour  — order is the board's left-to-right order
STATES=(
  "Inbox|backlog|#94a3b8"
  "Refining|unstarted|#a78bfa"
  "❓ Needs Answer|unstarted|#f59e0b"
  "Ready|unstarted|#60a5fa"
  "Planning|started|#a78bfa"
  "📋 Plan Review|started|#f59e0b"
  "In Progress|started|#a78bfa"
  "🔍 PR Review|started|#f59e0b"
  "🚀 Deploy Approval|started|#f59e0b"
  "Done|completed|#22c55e"
  "⚠️ Blocked|cancelled|#ef4444"
)

order=1
for entry in "${STATES[@]}"; do
  IFS='|' read -r name group colour <<<"$entry"
  echo "creating state: $name"
  curl -sf -X POST -H "X-API-Key: $PLANE_TOKEN" -H "Content-Type: application/json" \
    "$API" \
    -d "$(jq -nc --arg n "$name" --arg g "$group" --arg c "$colour" --argjson o "$order" \
          '{name:$n, group:$g, color:$c, sequence:($o * 1000)}')" \
    >/dev/null || echo "  (skipped — may already exist)"
  order=$((order + 1))
done

echo "done"
```

Make it executable: `chmod +x devflow/scripts/bootstrap-plane-board.sh`.

An amber colour marks every operator-owned gate state, so the board shows at a glance where you are the bottleneck.

- [ ] **Step 4: Run it**

```bash
./devflow/scripts/bootstrap-plane-board.sh
```

Expected: eleven `creating state:` lines with no errors.

- [ ] **Step 5: Verify every state exists with the right group**

```bash
curl -sf -H "X-API-Key: $PLANE_TOKEN" \
  "$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/$PLANE_PROJECT/states/" \
  | jq -r '.results | sort_by(.sequence) | .[] | "\(.name)\t\(.group)"'
```

Expected: exactly the eleven states in the spec's order, with groups `backlog, unstarted, unstarted, unstarted, started, started, started, started, started, completed, cancelled`.

Plane creates a set of default states on project creation. If you see extras (e.g. a default `Todo` or `Cancelled`), delete them through the UI so the Conductor cannot ever match the wrong state.

- [ ] **Step 6: Verify the ticket round-trip an agent will perform**

Create an issue, comment on it, and move it — the three operations the Conductor depends on:

```bash
ISSUE=$(curl -sf -X POST -H "X-API-Key: $PLANE_TOKEN" -H "Content-Type: application/json" \
  "$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/$PLANE_PROJECT/issues/" \
  -d '{"name":"Smoke test ticket"}' | jq -r '.id')

curl -sf -X POST -H "X-API-Key: $PLANE_TOKEN" -H "Content-Type: application/json" \
  "$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/$PLANE_PROJECT/issues/$ISSUE/comments/" \
  -d '{"comment_html":"<p>agent comment round-trip</p>"}' | jq -r '.id'
```

Expected: two UUIDs. Confirm the comment is visible in the UI, then delete the smoke-test ticket.

- [ ] **Step 7: Document and commit**

Add a `## Board topology` section to `devflow/README.md` with the eleven-state table from the spec and a note that the Conductor matches states **by name**, so renaming one is a breaking change.

```bash
git add devflow/scripts/bootstrap-plane-board.sh devflow/README.md
git commit -m "feat(devflow): add Plane board bootstrap script with the eleven workflow states"
```

---

### Task 8: Verify the Plane MCP server against the deployed instance

The spec's architecture assumes agents talk to the board through Plane's MCP server. Validating that now — against your actual Plane version — costs minutes; discovering it mid-Conductor-build costs a redesign.

**Files:**
- Create: `devflow/docs/plane-mcp-verification.md`

**Interfaces:**
- Consumes: running Plane, `$PLANE_TOKEN`, `$PLANE_WORKSPACE`.
- Produces: a recorded verdict on whether the MCP server works against this self-hosted instance, and the exact configuration block the agent runner image will use.

- [ ] **Step 1: Configure the MCP server locally**

Add to `~/.claude.json` (or run `claude mcp add`), pointing at the self-hosted instance:

```json
{
  "mcpServers": {
    "plane": {
      "command": "npx",
      "args": ["-y", "@makeplane/plane-mcp-server"],
      "env": {
        "PLANE_API_KEY": "REPLACE_WITH_PLANE_TOKEN",
        "PLANE_API_HOST_URL": "https://plane.homelab",
        "PLANE_WORKSPACE_SLUG": "REPLACE_WITH_WORKSPACE_SLUG"
      }
    }
  }
}
```

- [ ] **Step 2: Verify the server starts and lists tools**

```bash
claude mcp list
```

Expected: `plane` shown as connected. If it fails to connect, the most likely causes are the internal CA certificate not being trusted by Node (`NODE_EXTRA_CA_CERTS=/path/to/root_ca.crt`) or a wrong host URL.

- [ ] **Step 3: Exercise the four tools the Conductor depends on**

In a Claude Code session, confirm each works against the real board:

1. `list_projects` — returns the `DevFlow` project
2. `list_states` — returns the eleven states from Task 7
3. `create_work_item` — creates a ticket
4. `create_work_item_comment` — comments on it
5. `update_work_item` — moves it between states

- [ ] **Step 4: Record the verdict**

Write `devflow/docs/plane-mcp-verification.md` with the Plane version (from the UI footer), the MCP server version, which of the five operations succeeded, and any workarounds needed.

If the MCP server does **not** work against this instance, record that clearly — the fallback is that the agent runner calls Plane's REST API directly via `curl`, which Task 7 already proved works. This is a degradation in agent ergonomics, not a blocker.

- [ ] **Step 5: Commit**

```bash
git add devflow/docs/plane-mcp-verification.md
git commit -m "docs(devflow): record Plane MCP server verification against self-hosted instance"
```

---

### Task 9: Create the budget-capped LiteLLM virtual key

**Skip this task if Task 1 recorded a FAIL verdict** and instead configure a $50 monthly spend limit on the Anthropic API key in Anthropic's console, then document that in `devflow/README.md`.

**Files:**
- Modify: `devflow/README.md`

**Interfaces:**
- Consumes: running LiteLLM with the Anthropic model from Task 1.
- Produces: a virtual key with `max_budget: 50` and `budget_duration: "30d"`, stored as the swarm secret `devflow_agent_llm_key`. The agent runner uses this key exclusively.

- [ ] **Step 1: Generate the key**

First list the exact model names LiteLLM serves — the local Ollama models are registered in the database, so their names may not match the raw Ollama tags:

```bash
curl -sf http://litellm:4000/v1/models \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq -r '.data[].id'
```

Use the exact strings from that output in the `models` allowlist below (substituting for `LOCAL_MODEL_NAME`):

```bash
curl -sf -X POST "http://litellm:4000/key/generate" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key_alias": "devflow-agent",
    "models": ["claude-sonnet-5", "LOCAL_MODEL_NAME"],
    "max_budget": 50,
    "budget_duration": "30d",
    "rpm_limit": 60,
    "metadata": {"purpose": "devflow agent runner"}
  }' | jq -r '.key'
```

Expected: a `sk-...` key. Export it for the verification steps and store it as a secret:

```bash
export AGENT_KEY='PASTE_VIRTUAL_KEY'
printf '%s' "$AGENT_KEY" | docker secret create devflow_agent_llm_key -
```

- [ ] **Step 2: Verify the key works and is scoped**

```bash
curl -sf http://litellm:4000/v1/chat/completions \
  -H "Authorization: Bearer $AGENT_KEY" -H "Content-Type: application/json" \
  -d '{"model":"claude-sonnet-5","max_tokens":16,
       "messages":[{"role":"user","content":"Say OK"}]}' | jq -r '.choices[0].message.content'
```

Expected: `OK`.

Now confirm the model allowlist is actually enforced. Pick any model from the Step 1 listing that you did **not** put in the key's `models` array and request it:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://litellm:4000/v1/chat/completions \
  -H "Authorization: Bearer $AGENT_KEY" -H "Content-Type: application/json" \
  -d '{"model":"NOT_IN_ALLOWLIST","max_tokens":8,"messages":[{"role":"user","content":"hi"}]}'
```

Expected: a `400`-class status, not `200`. A `200` means the allowlist is not being applied and the budget cap may be equally unenforced — investigate before proceeding.

- [ ] **Step 3: Verify the budget is registered and spend accrues**

```bash
curl -sf "http://litellm:4000/key/info?key=$AGENT_KEY" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  | jq '.info | {key_alias, max_budget, budget_duration, spend}'
```

Expected: `max_budget: 50`, `budget_duration: "30d"`, and `spend` greater than zero after Step 2.

**This is the safety net for the entire project.** If `max_budget` reads `null`, the cap is not in force — do not run agents until it is.

- [ ] **Step 4: Test the failure mode you will actually rely on**

Create a throwaway key with a near-zero budget and confirm it fails closed:

```bash
TINY=$(curl -sf -X POST "http://litellm:4000/key/generate" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
  -d '{"key_alias":"budget-test","models":["claude-sonnet-5"],"max_budget":0.0001,"budget_duration":"30d"}' \
  | jq -r '.key')

for i in 1 2 3; do
  curl -s -o /dev/null -w "attempt $i: %{http_code}\n" http://litellm:4000/v1/chat/completions \
    -H "Authorization: Bearer $TINY" -H "Content-Type: application/json" \
    -d '{"model":"claude-sonnet-5","max_tokens":64,
         "messages":[{"role":"user","content":"Write a paragraph about databases."}]}'
done
```

Expected: the first call returns `200`, and a later call returns a budget-exceeded error status. Record the exact status code and error body — **the Conductor keys its `⚠️ Blocked` transition off this exact response shape.**

Clean up: `curl -sf -X POST http://litellm:4000/key/delete -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" -d "{\"keys\":[\"$TINY\"]}"`

- [ ] **Step 5: Document and commit**

Add a `## LLM budget` section to `devflow/README.md` recording the key alias, the cap, the exact budget-exceeded response shape observed in Step 4, and how to rotate the key.

```bash
git add devflow/README.md
git commit -m "docs(devflow): document budget-capped LiteLLM virtual key for agent runner"
```

---

### Task 10: Build a custom CI job image

**Why this exists.** The runner's default label maps to `node:20-bookworm-slim`,
which cannot build Go and lacks the tooling a React / React Native / Go monorepo
needs. Every workflow would otherwise re-install a toolchain on each run, which
is slow and makes CI results depend on upstream availability.

Pinning the toolchain in an image also makes CI reproducible: an agent that
passes tests today should pass them tomorrow for the same commit.

**Contents.** Driven by what Phase 2's workflows actually invoke — resist adding
anything speculative:

| Tool | Reason |
|---|---|
| Go | API build and `go test` |
| Node LTS + a pinned package manager | Web and mobile builds |
| `git`, `curl`, `ca-certificates` | `actions/checkout`, and trust for `gitea.homelab` |
| `golangci-lint` | Go static analysis gate |

React Native is the awkward part. A JS-only image covers lint, typecheck and
Jest, but **not** a device or simulator build — the verification gap already
recorded in the spec. Do not try to close it here; keep the image JS-only for
mobile and leave mobile UI verification at Gate 3.

> **SUPERSEDED 2026-07-30 — do not follow the steps below.** CI images are no
> longer built here or pinned to a runner label. They are owned by the projects
> that use them: each project keeps versioned Dockerfiles under its own `.ci/`,
> and Komodo builds and publishes them to `registry.homelab/<project>/`.
>
> This repo is infrastructure. An image in it means a toolchain bump — a
> decision belonging entirely to the application — needs an infrastructure pull
> request and a runner redeploy. That is the coupling the change removes.
>
> Design of record:
> [`.docs/superpowers/specs/2026-07-30-project-owned-ci-images-design.md`](../specs/2026-07-30-project-owned-ci-images-design.md).
>
> Three specifics below are actively wrong now:
> - **Label pinning** — workflows set `jobs.<id>.container.image`, which
>   act_runner honours ahead of the label. The label is only a fallback.
> - **Node registry credentials** — job images are pulled with credentials the
>   workflow supplies under `container.credentials`, so no node needs a standing
>   `docker login`.
> - **A committed root CA** — the step-ca root is copied into the build context
>   by Komodo's `pre_build` and verified against a pinned fingerprint. It is
>   never committed.

**Steps (historical).**

1. Write `devflow/ci-image/Dockerfile`. Pin every toolchain to an explicit
   version — no floating `latest`.
2. Build and push to the existing private registry:
   ```bash
   docker build -t registry.homelab/devflow-ci:<version> devflow/ci-image
   docker push registry.homelab/devflow-ci:<version>
   ```
3. Point the runner label at it in `devflow/config/gitea-runner-config.yaml`:
   ```yaml
   labels:
     - "homelab:docker://registry.homelab/devflow-ci:<version>"
   ```
4. Redeploy the runner. The label is written at registration, so confirm the
   change actually took in **Site Administration → Actions → Runners** rather
   than assuming it did.
5. Prove it: a workflow that runs `go version`, `node --version` and
   `actions/checkout` to `success`.

**Done when.** A workflow using the custom image reaches `success`, and the
image tag is recorded in `devflow/README.md`.

---

## What this plan deliberately leaves out

These belong to subsequent plans, each of which produces working software on its own:

| Plan | Scope | Spec phase |
|---|---|---|
| **Monorepo scaffold** | Go API, React web, React Native, OpenAPI generation, CI workflows | Phase 2 |
| **Conductor + agent runner** | The Go service, the runner image, the Refining phase, then remaining phases | Phases 3–4 |
| **Deploy automation** | Komodo integration at Gate 4 | Phase 5 |

## Done criteria for this plan

- Task 1 has a recorded PASS or FAIL verdict.
- `https://gitea.homelab` serves, and a workflow has actually run to `success` on the `homelab` runner.
- `https://plane.homelab` serves, with a `DevFlow` project whose states exactly match the spec's eleven.
- A ticket can be created and commented on through the Plane API.
- The MCP server verdict is recorded.
- A budget-capped virtual key exists, and its exhaustion behavior has been observed and documented.
- A workflow using the custom CI image has run to `success` on the `homelab` runner.

# llms

*   **`litellm`:** OpenAI-compatible gateway at `https://gtw.llm.homelab`.
*   **`open-webui`:** chat UI at `https://chat.llm.homelab`.

Both store their data in PostgreSQL on 192.168.5.30, in the `litellm` and `openwebui` databases. Local models come from Ollama on `zeus.ollama.homelab:11434`. LiteLLM reaches them through its `ollama_chat/` route, Ollama's chat API, which handles multi-turn conversations and tool calls. Models are listed in [`config/litellm-config.yaml`](config/litellm-config.yaml).

## Setup

```bash
mkdir -p /mnt/docker-data/services/litellm /mnt/docker-data/services/open-webui/uploads
cp config/litellm-config.yaml /mnt/docker-data/services/litellm/config.yaml
```

On the PostgreSQL primary:

```sql
CREATE DATABASE openwebui;
CREATE USER openwebui WITH PASSWORD '<password>';
GRANT ALL PRIVILEGES ON DATABASE openwebui TO openwebui;
CREATE DATABASE litellm;
CREATE USER litellm WITH PASSWORD '<password>';
GRANT ALL PRIVILEGES ON DATABASE litellm TO litellm;
```

`.env` next to `compose.yaml` (not committed):

```env
LITELLM_DB_USER=litellm
LITELLM_DB_PASSWORD=
LITELLM_MASTER_KEY=
ANTHROPIC_API_KEY=
WEBUI_DB_USER=openwebui
WEBUI_DB_PASSWORD=
WEBUI_SECRET_KEY=
```

## Deploy and check

```bash
docker stack deploy -c compose.yaml llms
docker service logs llms_litellm
```

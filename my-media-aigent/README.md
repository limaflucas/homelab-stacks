# my-media-aigent

Telegram bot that lets an LLM, through LiteLLM, manage requests in Seerr. Its source and image build live outside this repo.

*   **`my-media-aigent`:** the bot, image `registry.homelab/homelab/my-media-aigent:latest`. It talks to `litellm:4000` (model `gemma4:e4b`) over `llms_private` and to `seerr:5055` over `mouseion_private`.
*   **`whisper`:** CPU speech-to-text (`hwdsl2/whisper-server`, `base` model, int8). Models are cached in `/mnt/docker-data/services/my-media-aigent/whisper`.

## Setup and deploy

```bash
echo "<seerr api key>" | docker secret create overseerr_api_key -
echo "<telegram bot token>" | docker secret create telegram_bot_token -
echo "<whisper api key>" | docker secret create whisper_api_key -
```

The compose file also reads `LITELLM_API_KEY`, `OVERSEERR_API_KEY`, `TELEGRAM_BOT_TOKEN` and `WHISPER_API_KEY`. They're kept in the Komodo stack's environment. To deploy by hand, put them in a `.env` next to `compose.yaml` (not committed):

```bash
set -a; . ./.env; set +a
docker stack deploy -c compose.yaml my-media-aigent
```

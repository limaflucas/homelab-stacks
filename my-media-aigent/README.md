# my-media-aigent

Telegram bot that lets an LLM, through LiteLLM, manage requests in Seerr. Its source is [`homelab/my-media-aigent`](https://gitea.homelab/homelab/my-media-aigent) on Gitea.

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

## Build and deploy on push

A push to `master` fires the repo's Gitea webhook, which runs the Komodo procedure `my-media-aigent`:
1.  **Clone:** the Komodo repo `my-media-aigent`, on `vm-docker-bragi`.
2.  **Build:** the Komodo build `my-media-aigent` pushes `registry.homelab/homelab/my-media-aigent` tagged `latest`, the next version and the short commit.
3.  **Deploy:** this stack, which pulls `latest`.

*   **Webhook:** `https://komodo.homelab/listener/github/procedure/my-media-aigent/master`, type Gitea, push events, branch filter `master`. Its secret is the procedure's own webhook secret, not `KOMODO_WEBHOOK_SECRET`.
*   **Git access:** Komodo clones as the Gitea user `komodo`, a restricted account with read access to this repo only. Its `read:repository` token is in Komodo's `gitea.homelab` git account.

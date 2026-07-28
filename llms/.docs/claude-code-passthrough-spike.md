# Spike: Claude Code through LiteLLM — Anthropic passthrough

**Date:** 2026-07-28
**Verdict:** ✅ **PASS**
**Relates to:** `.docs/superpowers/plans/2026-07-28-devflow-infrastructure.md` — Task 1

## Question

Does LiteLLM expose an Anthropic-format passthrough, so that agent runners can
point `ANTHROPIC_BASE_URL` at the proxy and have every token metered and
budget-capped by a LiteLLM virtual key?

This was the least certain assumption in the design spec. If it failed, agent
runners would have to call `api.anthropic.com` directly, moving budget
enforcement to Anthropic's console and forcing the Conductor to poll usage
instead of catching a clean budget error.

## Setup

- LiteLLM `ghcr.io/berriai/litellm-database:main-stable`, `llms` stack.
- `ANTHROPIC_API_KEY` supplied via the stack's `.env` convention (not a swarm
  secret — matches how `LITELLM_MASTER_KEY` is already handled).
- Models declared in `llms/config/litellm-config.yaml`: `claude-sonnet-5` and
  `claude-haiku-4-5` on `anthropic/`, plus five local Ollama models on
  `ollama_chat/`.

## Results

**OpenAI-format route** (`/v1/chat/completions`) — verified via the LiteLLM
admin playground. Both Anthropic models respond correctly.

**Anthropic-format passthrough** (`/anthropic/v1/messages`) — verified by
direct call from inside the container:

```bash
CID=$(docker ps -qf name=llms_litellm)
docker exec -it $CID sh -c 'curl -s http://localhost:4000/anthropic/v1/messages \
  -H "x-api-key: $LITELLM_MASTER_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d "{\"model\":\"claude-sonnet-5\",\"max_tokens\":16,
       \"messages\":[{\"role\":\"user\",\"content\":\"Say OK\"}]}"'
```

Response (HTTP 200):

```json
{
  "model": "claude-sonnet-5",
  "id": "msg_011CdVJyxFuN6KpUnwK3Augq",
  "type": "message",
  "role": "assistant",
  "content": [{"type": "text", "text": "OK"}],
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 10,
    "output_tokens": 4,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "service_tier": "standard",
    "inference_geo": "global"
  }
}
```

This is a native Anthropic Messages API response shape — `stop_reason`,
`usage`, and `inference_geo` are all present and pass through unmodified.

## Consequences

- **Agent runners set `ANTHROPIC_BASE_URL=http://litellm:4000/anthropic`** and
  `ANTHROPIC_AUTH_TOKEN` to their LiteLLM virtual key. Claude Code appends
  `/v1/messages` to the base URL, which is exactly the verified path.
- **Budget enforcement stays in LiteLLM.** Task 9 of the plan proceeds as
  written: a virtual key with `max_budget: 50` and `budget_duration: "30d"`.
- **The Conductor detects exhaustion from the API error response**, not by
  polling a usage endpoint.
- Prompt caching fields are present in `usage`, so the cost model's assumption
  that cached reads are observable and meterable holds.

## Follow-up

Spend attribution was not separately verified in this spike. Before the agent
runner goes live, confirm that calls made with a virtual key accrue against
that key:

```bash
curl -s "http://localhost:4000/key/info?key=$AGENT_KEY" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.info.spend'
```

Note `proxy_batch_write_at: 60` in the config — spend is written in batches, so
allow a minute before expecting a non-zero value. This is covered by Task 9,
Step 3.

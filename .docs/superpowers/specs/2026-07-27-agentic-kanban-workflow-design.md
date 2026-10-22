# AI-Centric Kanban Agent Workflow — Design

**Date:** 2026-07-27
**Status:** Approved design, ready for implementation planning
**Author:** Lucas Lima, with Claude

## Problem

Build a workflow where AI agents pick up small, well-scoped tasks, ask clarifying
questions, implement and test them, and open pull requests — all coordinated
through a kanban board that a single human operator watches and steers. The
workflow must run on the existing Docker Swarm homelab and route all model
traffic through the existing LiteLLM proxy.

The first target is a greenfield application: a React web client and a React
Native mobile client sharing a Go backend, in a monorepo.

## Constraints

These are fixed inputs, not decisions made during design:

| Constraint | Value |
|---|---|
| Infrastructure | 3-node Docker Swarm (`adam`, `bragi`, `zeus`) |
| Model gateway | Existing LiteLLM at `litellm:4000`, Postgres-backed |
| Cloud LLM budget | Under $50/month, hard cap |
| Human gates | All four: clarification, plan approval, PR review, deploy approval |
| Code hosting | Self-hosted Gitea on the swarm |
| Agent execution | Containers on the swarm, not the operator's laptop |
| Repo layout | Monorepo |

### Existing infrastructure this design builds on

- **Postgres HA** via `pgpool` — Plane and Gitea use it; no new database stack.
- **MinIO** — Plane attachment storage.
- **Nginx Proxy Manager + Authelia** — ingress and SSO for the new web UIs.
- **`registry.homelab`** — private registry for the agent runner image.
- **Komodo** — already deployed; drives redeploys at the final gate.
- **Ollama on `zeus.ollama.homelab`** — `gemma4:12b`, `llama3.1:8b`,
  `qwen2.5-coder:7b`. Useful for triage and summarization, **not** capable of
  autonomous agentic coding. This is why cloud model access is required.

## Non-goals

- Agents deploying to production without human approval.
- Agents verifying React Native UI behavior (see Testing, below).
- Replacing the operator's judgment on scope, architecture, or merge decisions.
- A general-purpose agent platform. This workflow serves one monorepo.

---

## Definition of Ready — the "tiny task" boundary

A ticket may leave `Refining` only if it is **one user-visible capability** that
satisfies all of:

- ≤ ~400 changed lines, ≤ 8 files
- touches at most **one** Go domain package, **one** web screen/component, and
  **one** mobile screen
- acceptance criteria expressible as **≤ 5 testable assertions**
- does not combine a schema migration *and* a new endpoint *and* two client UIs

A ticket needing all three of that last clause is an epic. The agent proposes a
split and moves it back to `Inbox` rather than attempting it.

This boundary is deliberately generous enough to ship a vertical slice (user
value per ticket) while staying inside the window where agents reliably succeed.

## Definition of Done

A ticket reaches `Done` only when: CI is green on the merged commit, the PR was
reviewed and merged by the operator, Komodo has redeployed the affected stack,
and — for any ticket touching mobile — the operator has confirmed the change on
a device.

---

## Architecture

```
     Operator (browser + Telegram)
            │
            ▼
   ┌─────────────────┐  webhook   ┌──────────────┐
   │  Plane          │───────────▶│  Conductor   │
   │  board + API    │◀───────────│  (Go)        │
   └─────────────────┘  MCP/API   └──────┬───────┘
                                         │ docker service create (one-shot job)
                                         ▼
                                ┌──────────────────┐
                                │  Agent Runner    │  ephemeral, one per phase
                                │  Claude Code     │
                                │  + Plane MCP     │
                                │  + repo checkout │
                                └────┬────────┬────┘
                                     │        │
                          ┌──────────▼──┐  ┌──▼──────────────┐
                          │ LiteLLM     │  │ Gitea +         │
                          │ (existing)  │  │ act_runner      │
                          │ BUDGET CAP  │  └──────┬──────────┘
                          └─────────────┘         │ merge
                                                  ▼
                                            Komodo → swarm
```

### Components

| # | Component | New? | Responsibility |
|---|---|---|---|
| 1 | **Plane** | New stack | Kanban board; single source of truth for task state. Postgres on pgpool, attachments in MinIO, behind NPM + Authelia. |
| 2 | **Gitea + `act_runner`** | New stack | Monorepo hosting and CI. Same Postgres cluster. |
| 3 | **Conductor** | New Go service | Receives Plane webhooks, decides which agent phase to launch, spawns a swarm job, tracks it, notifies via Telegram. |
| 4 | **Agent Runner** | New image | Container with Claude Code (headless), the repo, Go/Node toolchains, and the Plane MCP server. One container per phase-run, destroyed after. |
| 5 | **LiteLLM** | Existing | Model routing and — critically — budget enforcement via a virtual key. |
| 6 | **Komodo** | Existing | Redeploys stacks on operator approval. |

Only the Conductor is written from scratch (~600 lines of Go).

### The runtime seam

The Conductor talks to the agent runtime through exactly one interface:

```go
type Runtime interface {
    Run(ctx context.Context, spec TaskSpec) (TaskResult, error)
}
```

`ClaudeCodeRuntime` implements it. A future `LangGraphRuntime` (the
custom-agent-graph approach considered and deferred) would be a new
implementation and one line of wiring. Nothing else in the system knows which
runtime is in use.

---

## Board topology

**Organizing principle: every state is owned unambiguously by either the operator
or an agent.** No state is ambiguous about who acts next. The four human gates
are the four operator-owned states.

| # | State | Group | Owner | Meaning |
|---|-------|-------|-------|---------|
| 1 | **Inbox** | Backlog | Operator | A rough idea. One sentence is acceptable. |
| 2 | **Refining** | Unstarted | Agent | Agent checks the ticket against Definition of Ready and posts clarifying questions as a comment. |
| 3 | **❓ Needs Answer** | Unstarted | **Operator** | **Gate 1.** Operator replies in comments. Telegram ping. |
| 4 | **Ready** | Unstarted | Agent | Spec is precise, sized, and has acceptance criteria. |
| 5 | **Planning** | Started | Agent | Agent explores the repo and drafts an implementation plan. |
| 6 | **📋 Plan Review** | Started | **Operator** | **Gate 2.** Plan posted as a comment. Telegram ping. |
| 7 | **In Progress** | Started | Agent | Agent implements, runs tests, iterates until green. |
| 8 | **🔍 PR Review** | Started | **Operator** | **Gate 3.** PR open on Gitea, CI green. Telegram ping with diff stat. |
| 9 | **🚀 Deploy Approval** | Started | **Operator** | **Gate 4.** Merged to `main`. Operator approves the redeploy. |
| 10 | **Done** | Completed | — | Deployed and verified. |
| 11 | **⚠️ Blocked** | Cancelled | **Operator** | Agent hit a wall, exhausted retries, or the budget is exhausted. Agent's notes explain why. |

### State transition protocol

- **Approval is expressed by moving the card**, not by comment parsing. Dragging
  is unambiguous, produces a single webhook event, and is the natural kanban
  gesture. Comments carry *content*; state carries *decisions*.
- At Gate 1 the operator answers in comments, then drags to `Ready`. If the
  answer implies work beyond the size envelope, the agent moves the ticket back
  to `Refining` and proposes a split into two tickets.
- The Conductor only ever acts on a transition **into** an agent-owned state. A
  transition into an operator-owned state is terminal for the agent.

### Failure and retry policy

- An agent phase-run that exits non-zero is retried **once**.
- A second failure moves the ticket to `⚠️ Blocked` with the runner's log tail
  posted as a comment.
- A LiteLLM budget-exhausted error moves the ticket to `⚠️ Blocked` immediately
  with no retry, and sends a distinct Telegram message.
- The Conductor never leaves a ticket in an agent-owned state with no running
  job; a reconciliation loop on startup moves orphans to `⚠️ Blocked`.

---

## Cost model

**Pricing (verified 2026-07-27):** Claude Sonnet 5 is $3 / $15 per million input
/ output tokens, with an introductory rate of **$2 / $10 through 2026-08-31**.
Claude Haiku 4.5 is $1 / $5. Cache reads cost ~0.1× the input rate; cache writes
1.25×.

Estimated cost of one agent phase-run on a right-sized ticket:

| Component | Tokens | Rate | Cost |
|---|---|---|---|
| Cached input reads | 400K | $0.20/M | $0.08 |
| Fresh input | 100K | $2.00/M | $0.20 |
| Output | 40K | $10.00/M | $0.40 |
| **Total per phase-run** | | | **~$0.68** |

Refining runs on a local model at zero marginal cost, so a ticket costs roughly
two cloud phase-runs — Planning (lighter) and In Progress (heavier), plus
retries: **$1.50–3.00 per ticket**. The $50/month cap therefore supports
approximately **20–30 tickets per month**.

### Cost levers, in order of impact

1. **Model routing in LiteLLM.** Refining, triage, and summarization route to
   local `gemma4:12b` at zero marginal cost. Only Planning and In Progress use
   Sonnet 5. No cloud tokens are spent on a ticket that has not passed Gate 1.
2. **Prompt caching.** The monorepo's `CLAUDE.md`, architecture notes, and test
   conventions form a stable prefix and must be cached. Without caching, the
   cached-reads row above costs $0.80 instead of $0.08 and per-ticket cost
   roughly doubles.
3. **Human gates.** Killing a bad plan at Gate 2 costs ~$0.20 instead of ~$3.00.

### Budget enforcement

The agent's LiteLLM virtual key is created with `max_budget: 50` and
`budget_duration: "30d"`. When exhausted, agent runs fail closed with a budget
error rather than producing a surprise invoice. This is the single most
important reason LiteLLM is load-bearing in this design rather than incidental.

---

## Testing and release

### CI gates by layer

An agent may move a ticket to `🔍 PR Review` only when Gitea CI is green. **CI is
the arbiter, not the agent's own assessment of its work.**

| Layer | Gate |
|---|---|
| Go API | `go test ./...`, `go vet`, `golangci-lint` |
| React web | `vitest run`, `tsc --noEmit`, `eslint` |
| React Native | `jest`, `tsc --noEmit` — unit tests only |
| Contract | OpenAPI-generated clients regenerated and committed; CI fails on a dirty diff |

### Known limitation: mobile UI verification

Agents cannot meaningfully verify React Native UI. There is no simulator, no
device, and no visual check available in the runner container. Consequently,
Definition of Done for any mobile-touching ticket requires the operator to
confirm the change on a device at Gate 3. This is stated explicitly rather than
papered over. The Go API is the layer where this workflow delivers the most
value, because it is fully verifiable inside a container.

### Contract-first monorepo

The Go API owns an OpenAPI specification; the web and mobile clients are
generated from it. An agent changing an endpoint regenerates both clients within
the same PR, and the type checker catches every missed call site. Without this,
cross-stack tickets degrade into guesswork.

### Release path

Merge to `main` → Gitea webhook → Conductor moves the ticket to
`🚀 Deploy Approval` → operator drags the card → Conductor calls the Komodo API →
Komodo pulls and redeploys the stack. Rollback is redeploying the previous image
tag, which Komodo already supports.

---

## Risks

| Risk | Mitigation |
|---|---|
| **Claude Code may not route through LiteLLM's Anthropic passthrough.** This is the least certain assumption in the design. | Phase 0 is a spike that proves or disproves it before anything is built. Documented fallback: the runner calls the Anthropic API directly and budget enforcement moves to Anthropic's console limits. Everything else in the design is unaffected. |
| Three new stacks (Plane, Gitea, CI runner) is real operational surface. | Phase 1 delivers them standalone; they are useful on their own even if the agent work stalls. |
| Agents produce plausible-looking but wrong code. | Four human gates; CI as the arbiter; small ticket envelope. |
| Budget exhausted mid-month. | Hard cap fails closed with a distinct notification; tickets park in `⚠️ Blocked`. |
| Plane's self-hosted API diverges from the MCP server's expectations. | The MCP server documents support for self-hosted instances. Phase 1 validates against the actual deployed version before the Conductor depends on it. |

---

## Rollout phases

| Phase | Deliverable | Rationale |
|---|---|---|
| **0** | Spike: prove Claude Code routes through LiteLLM's Anthropic passthrough. | ~30 minutes. Everything downstream assumes it. |
| **1** | Deploy Plane, Gitea, and `act_runner` stacks; create the 11 board states. | Pure infrastructure, no agents. Yields a working board and self-hosted Git immediately. |
| **2** | Scaffold the monorepo: Go API, React, React Native, CI pipeline, OpenAPI generation. | Needed regardless of agents. Built by hand, carefully. |
| **3** | Conductor + agent runner, **Refining phase only**. | The smallest complete agent loop. Proves the entire plumbing at minimal token cost. The real milestone. |
| **4** | Add Planning, In Progress, and PR phases. | Now a complete workflow. |
| **5** | Deploy automation via Komodo. | Last, because it is the only irreversible step. |

---

## Reference documentation

### Plane
- Self-hosting guide — https://developers.plane.so/self-hosting/overview
- REST API reference — https://developers.plane.so/api-reference/introduction
- Webhooks — https://developers.plane.so/api-reference/webhook/webhooks
- Source — https://github.com/makeplane/plane
- **MCP server** (agent-native board access) — https://github.com/makeplane/plane-mcp-server
- Node SDK (reference for API shapes) — https://github.com/makeplane/plane-node-sdk

### LiteLLM
- Proxy documentation — https://docs.litellm.ai/docs/simple_proxy
- Virtual keys and budgets — https://docs.litellm.ai/docs/proxy/virtual_keys
- Budgets and rate limits — https://docs.litellm.ai/docs/proxy/users
- Model routing and fallbacks — https://docs.litellm.ai/docs/routing
- Prometheus metrics (budget gauges) — https://docs.litellm.ai/docs/proxy/prometheus

### Gitea
- Documentation — https://docs.gitea.com/
- Gitea Actions — https://docs.gitea.com/usage/actions/overview
- `act_runner` setup — https://docs.gitea.com/usage/actions/act-runner
- Webhooks — https://docs.gitea.com/usage/webhooks

### Claude / Anthropic
- Claude Code overview — https://code.claude.com/docs/en/overview
- Claude Code headless mode — https://code.claude.com/docs/en/headless
- Claude Agent SDK — https://code.claude.com/docs/en/agent-sdk
- Model overview and pricing — https://platform.claude.com/docs/en/about-claude/models/overview
- Prompt caching — https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Model Context Protocol — https://modelcontextprotocol.io/

### Infrastructure
- Docker Swarm services — https://docs.docker.com/engine/swarm/services/
- Docker Swarm one-shot jobs (`--mode replicated-job`) — https://docs.docker.com/reference/cli/docker/service/create/
- Komodo — https://komo.do/docs/intro
- Docker Engine API (Go client) — https://pkg.go.dev/github.com/docker/docker/client

### Background reading on agentic workflows
- Anthropic, "Building effective agents" — https://www.anthropic.com/engineering/building-effective-agents
- Anthropic, "Writing tools for agents" — https://www.anthropic.com/engineering/writing-tools-for-agents

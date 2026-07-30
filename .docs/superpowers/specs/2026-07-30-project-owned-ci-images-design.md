# Project-Owned CI and Runtime Images — Design

**Date:** 2026-07-30
**Status:** Approved design, ready for implementation planning
**Author:** Lucas Lima, with Claude

## Problem

The devflow stack currently carries three CI job images in
`devflow/ci-images/{api,web,mobile}/Dockerfile`, published as
`registry.homelab/homelab/devflow-ci-*`. Each runner config pins one tag:

```yaml
# devflow/config/gitea-runner-api.yaml:19
labels:
  - "homelab-api:docker://registry.homelab/homelab/devflow-ci-api:1.0.0"
```

This puts application artifacts inside the infrastructure repo. Bumping Go,
pnpm, or golangci-lint — a decision that belongs entirely to the application —
requires a homelab pull request and a runner redeploy. The homelab repo should
concern itself only with the infrastructure that runs projects.

The trigger for addressing this now is the `shopper` monorepo, cloned to
`/Users/lflima/Vault/shopper` from `ssh://git@gitea.homelab:2222/Homelab/shopper.git`.
It is the first real consumer, and it is still empty, so the boundary can be
drawn before anything depends on the wrong side of it.

## Constraints

These are fixed inputs, not decisions made during design:

| Constraint | Value | Source |
|---|---|---|
| homelab repo scope | Infrastructure only — no application artifacts | Stated principle |
| Builder | Komodo, already deployed | `infra/compose.yaml:295` |
| Registry | `registry.homelab`, **htpasswd auth required** | `infra/compose.yaml:514-516` |
| Runner Docker socket | Never mounted into job containers | `docker_host: "-"` |
| Komodo webhook filtering | Branch only — no path or content filter | Komodo API |
| Runner image pull policy | `force_pull: false` | Runner configs |
| Web testing | Unit/component (Vitest/Jest) **and** browser E2E (Playwright) | Decided |
| Deliverables | Both CI images and deployable runtime images | Decided |

### The socket constraint is not negotiable

`docker_host: "-"` means job containers get no Docker socket. The comment in
`gitea-runner-api.yaml:36-39` gives the reason: workflow code is agent-authored,
and a mounted socket is root on the node.

Branch protection does not mitigate this. `runs-on:` is a string an agent types,
and the danger materialises at run time, not merge time — a workflow on an
unmerged branch still executes. So the runners cannot build images, and the
builder must live outside them. This is what makes Komodo load-bearing rather
than merely convenient.

## Non-goals

- Standing up a second builder (BuildKit, Kaniko) alongside Komodo.
- Granting runners Docker access under any conditions.
- Enabling the runner cache. Still deferred, for the reasons in
  `gitea-runner-api.yaml:21-26`.
- Publishing images for anything outside `shopper`.

---

## 1. Ownership split

**homelab provides capabilities. shopper provides artifacts.**

| Concern | Owner |
|---|---|
| Gitea, runners, Komodo, registry | homelab |
| Dockerfiles (CI and runtime) | shopper |
| Toolchain versions and image tags | shopper |
| Build trigger workflows | shopper |
| Registry credentials (as Gitea secrets) | homelab, consumed by shopper |

A Go or pnpm bump becomes a shopper pull request that touches homelab not at
all. That is the test this design has to pass.

Images are namespaced by project, so the boundary is visible in the registry
itself: `registry.homelab/shopper/ci-api`, not
`registry.homelab/homelab/devflow-ci-api`. The current `homelab/` namespace is
the artifact-in-infrastructure problem spelled out in the image name.

## 2. Repository layout

```
shopper/
├── .ci/
│   ├── shared/homelab-root-ca.crt   # public step-ca root; committing is intended
│   ├── api/Dockerfile               # CI: Go + golangci-lint
│   ├── web/Dockerfile               # CI: Playwright base + pnpm
│   ├── mobile/Dockerfile            # CI: Node + pnpm
│   └── versions.env                 # single source of truth for image tags
├── .gitea/workflows/
│   ├── ci-images.yaml               # path-filtered; triggers Komodo
│   ├── api.yaml                     # lint + test the Go API
│   └── web.yaml                     # unit tests + Playwright E2E
├── deploy/
│   ├── api/Dockerfile               # runtime: distroless, Go binary
│   └── web/Dockerfile               # runtime: nginx + static dist
```

`.ci/` and `deploy/` are separate because they have different lifecycles and
different triggers. CI images change when the toolchain changes — rarely.
Runtime images change on every application commit. Collapsing them into one
directory would force one path filter to serve two very different cadences.

`versions.env` holds every image tag in one file:

```sh
CI_API_VERSION=1.0.0
CI_WEB_VERSION=1.0.0
CI_MOBILE_VERSION=1.0.0

# Base-image pin for ci-web. Must equal the @playwright/test version in
# package.json — see the lockstep constraint below. Value is set in Stage 2,
# when package.json first exists; the number here is illustrative.
PLAYWRIGHT_VERSION=1.56.0
```

Workflows read it, so a tag appears in exactly one place. Without this, the tag
lives in both the workflow's `container.image` and the build trigger, and the
two drift.

## 3. Image inventory

### CI images

| Image | Base | Contents |
|---|---|---|
| `shopper/ci-api` | `golang:1.26.5-bookworm` | golangci-lint 2.12.2, `GOTOOLCHAIN=local` |
| `shopper/ci-web` | `mcr.microsoft.com/playwright:v<ver>-noble` | pnpm via corepack, browsers preinstalled |
| `shopper/ci-mobile` | `node:22.23.2-bookworm-slim` | pnpm via corepack |

The existing `devflow/ci-images/{api,mobile}/Dockerfile` move essentially
unchanged — the pinning discipline, the checksum-verified golangci-lint install,
and the verification layer that fails the build when a toolchain does not match
its pin are all worth keeping. Only the CA path and image name change.

`ci-web` is rebased. Today it derives from `node:22.23.2-bookworm-slim`, which
carries no browsers. Installing Chromium and its system libraries per run costs
minutes on every job, and `cache.enabled: false` means that cost is paid every
time. Microsoft's Playwright image ships the browsers and the system
dependencies already matched to a Playwright release.

Mobile gets no runtime image — React Native emits an APK/IPA, not a container.

### Runtime images

| Image | Base | Notes |
|---|---|---|
| `shopper/api` | `gcr.io/distroless/static` | Multi-stage; static Go binary |
| `shopper/web` | `nginx:alpine` | Multi-stage; serves built `dist/` |

## 4. The Playwright lockstep constraint

Playwright refuses to run when the browsers on disk do not match the
`@playwright/test` version that drives them. The failure surfaces as
`Executable doesn't exist at /ms-playwright/chromium-XXXX`, which points at the
image and says nothing about `package.json` — the cause and the symptom are in
different repositories' worth of context.

This makes the coupling mandatory: **bumping `@playwright/test` in `package.json`
requires rebuilding `ci-web` on the matching base tag.**

Rather than document that as a rule someone remembers, the web CI workflow
asserts it:

```yaml
- name: Assert Playwright image matches package.json
  run: |
    pkg=$(jq -r '.devDependencies."@playwright/test"' package.json | tr -d '^~')
    img=$(printf '%s' "$PLAYWRIGHT_VERSION")
    test "$pkg" = "$img" || {
      echo "package.json wants Playwright $pkg but this image ships $img."
      echo "Bump PLAYWRIGHT_VERSION in .ci/versions.env and rebuild ci-web."
      exit 1
    }
```

`PLAYWRIGHT_VERSION` is baked into the image as an env var at build time, so the
check compares the repo's declared version against what the image actually
carries. This converts a confusing runtime failure into a build-time message
that names the fix.

## 5. Build trigger flow

```
shopper push touching .ci/**
  └─ .gitea/workflows/ci-images.yaml     ← supplies the path filter Komodo lacks
       ├─ guard: tag must not already exist in the registry
       └─ curl → Komodo build webhook
            └─ Komodo clones, builds, pushes → registry.homelab/shopper/*
```

Komodo's webhooks filter by branch only. A thin path-filtered workflow supplies
the missing filter and needs no Docker socket to do it — it only makes an HTTP
request. It runs in a public `curlimages/curl` image, so there is no bootstrap
loop where building the CI image requires the CI image.

One Komodo Build resource per image, each configured with:

- Gitea as a custom git provider, repo `Homelab/shopper`
- `image_registry` pointing at `registry.homelab/shopper`
- `webhook_enabled: true` with a per-build `webhook_secret`
- Dockerfile path and build context per the layout above

### Tag immutability needs enforcement, not convention

`force_pull: false` means a node holding a cached tag never re-pulls it. If a
Dockerfile changes without a version bump, Komodo overwrites the tag and nodes
silently disagree about what CI is running — one node tests against the old
toolchain, another against the new, and the difference shows up as a flaky test
rather than as a configuration error.

The guard step makes this loud:

```yaml
- name: Refuse to overwrite an existing tag
  run: |
    if curl -sSf -u "$REG_USER:$REG_PASS" \
         "https://registry.homelab/v2/shopper/ci-api/manifests/$CI_API_VERSION" \
         -H 'Accept: application/vnd.oci.image.manifest.v1+json' >/dev/null 2>&1; then
      echo "Tag $CI_API_VERSION already published. Bump it in .ci/versions.env."
      exit 1
    fi
```

A registry HEAD request is cheap, and failing here costs seconds instead of
debugging cross-node drift later.

## 6. Runner consolidation

The three runners exist only to map three labels to three images. Once shopper's
workflows name their own image, that mapping is dead weight.

**Verified against act_runner source:** `ContainerSpec` parses `image:` from
workflow YAML, and `RunContext.IsHostEnv` treats a non-empty `containerImage()`
as decisive over the label-derived platform from `runsOnImage()`. A job's
`container.image` therefore wins over the label default.

So homelab collapses from three runner services to one:

```yaml
# devflow/config/gitea-runner.yaml
runner:
  capacity: 5          # was 2 + 2 + 1 across three runners
  labels:
    - "homelab:docker://docker.gitea.com/runner-images:ubuntu-24.04"
```

The label's image becomes a neutral fallback rather than a project pin. Shopper
workflows select their own:

```yaml
jobs:
  test:
    runs-on: homelab
    container:
      image: registry.homelab/shopper/ci-api:1.0.0
      credentials:
        username: ${{ secrets.REGISTRY_USERNAME }}
        password: ${{ secrets.REGISTRY_PASSWORD }}
```

Net effect: three services become one, homelab stops encoding anything
project-specific, and a toolchain bump is a one-line shopper change.

### Registry credentials

`registry.homelab` requires htpasswd auth (`infra/compose.yaml:514-516`). The
current arrangement works only because each node has been `docker login`-ed by
hand — undocumented state that a rebuilt node silently loses, surfacing as an
image pull failure with no obvious cause.

The `credentials:` block above replaces that with explicit, declared
authentication. `REGISTRY_USERNAME` and `REGISTRY_PASSWORD` are set once as
Gitea **organisation-level** secrets, so every repo in `Homelab` inherits them.
This removes a hidden node-level dependency rather than adding a new one.

## 7. Sequencing

Shopper is empty — one commit, an 11-byte README. There is no `package.json`,
so `ci-web`'s Playwright assertion has nothing to check against yet.
Implementation therefore lands in two stages.

**Stage 1 — prove the path with `ci-api`.** Go has no version-coupling
equivalent, so it isolates the pipeline from application concerns. This stage
delivers: `.ci/` scaffolding, `versions.env`, the Komodo Build resource, the
trigger workflow with its tag guard, the consolidated runner, and org-level
registry secrets. Success means a `.ci/api/Dockerfile` commit produces a
published `registry.homelab/shopper/ci-api:1.0.0` with no homelab change.

**Stage 2 — web and mobile, with the Phase 2 monorepo scaffold.** Adds `ci-web`
on the Playwright base with its version assertion, `ci-mobile`, and both runtime
images. Deferred because each needs application code that does not exist yet.

Once Stage 1 is verified, `devflow/ci-images/` is deleted from homelab and the
three runner configs are replaced by one.

## 8. Error handling

| Failure | Surfaces as | Recovery |
|---|---|---|
| Tag already published | Trigger workflow fails with the bump instruction | Bump `versions.env` |
| Playwright version mismatch | CI job fails naming both versions | Bump `PLAYWRIGHT_VERSION`, rebuild `ci-web` |
| Registry auth failure | Pull fails in job container | Verify org-level Gitea secrets |
| Komodo build failure | Komodo UI; trigger workflow already green | Read Komodo build log |
| Webhook unreachable | `curl` fails the trigger job | Check Komodo Core health |

The webhook is fire-and-forget: the trigger workflow reports that Komodo was
asked to build, not that the build succeeded. Build outcomes live in Komodo.
Coupling them would mean polling Komodo from a workflow, which buys little given
that a failed build simply means the tag never appears — and the tag guard
catches that on the next attempt.

## 9. Open items for the implementation plan

- Exact Komodo Build resource fields for a Gitea custom git provider.
- Whether Komodo pushes to `registry.homelab` via a stored account or an
  injected credential.
- The `noble` vs `jammy` suffix on the Playwright base tag, fixed at the moment
  the version is chosen.
- Whether `capacity: 5` holds on `vm-docker-adam`. Job containers are non-swarm
  siblings, so the runner service's `memory: 2G` limit does not bound them —
  five concurrent Playwright jobs are unbounded on the node. Worth watching
  before raising further, per the existing note in the runner config.

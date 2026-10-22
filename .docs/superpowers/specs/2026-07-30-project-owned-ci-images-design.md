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
│   ├── api/Dockerfile               # CI: Go + golangci-lint
│   ├── web/Dockerfile               # CI: Playwright base + pnpm
│   ├── mobile/Dockerfile            # CI: Node + pnpm
│   └── versions.env                 # single source of truth for image tags
├── .gitea/workflows/
│   ├── ci-images.yaml               # path-filtered; triggers Komodo
│   ├── api.yaml                     # lint + test the Go API
│   └── web.yaml                     # unit tests + Playwright E2E
├── .cd/
│   ├── api/Dockerfile               # runtime: distroless, Go binary
│   └── web/Dockerfile               # runtime: nginx + static dist
```

No committed certificate — see §4a. `.ci/` and `.cd/` are separate because they
have different lifecycles and different triggers. CI images change when the
toolchain changes — rarely. Runtime images change on every application commit.
Collapsing them into one directory would force one path filter to serve two very
different cadences.

`versions.env` holds every image tag in one file:

```sh
CI_API_VERSION=1.0.0
CI_WEB_VERSION=1.0.0
CI_MOBILE_VERSION=1.0.0

# Base-image pin for ci-web. Must equal the @playwright/test version in
# package.json — see the lockstep constraint below. Value is set in Stage 2,
# when package.json first exists; the number here is illustrative.
PLAYWRIGHT_VERSION=1.56.0

# SHA-256 over the DER encoding of the step-ca root — see §4a.
STEP_CA_FINGERPRINT=8e0babaaed6ac699d4455892a4759c1e0b51102cc733d776320ad30d20259ca6
```

Workflows read it, so a tag appears in exactly one place. Without this, the tag
lives in both the workflow's `container.image` and the build trigger, and the
two drift.

## 3. Image inventory

### CI images

| Image | Base | Contents |
|---|---|---|
| `shopper/ci-api` | `golang:1.26.5-alpine` | golangci-lint 2.12.2, `GOTOOLCHAIN=local` |
| `shopper/ci-web` | `mcr.microsoft.com/playwright:v<ver>-noble` | pnpm via corepack, browsers preinstalled |
| `shopper/ci-mobile` | `node:22.23.2-alpine` | pnpm via corepack |

The existing `devflow/ci-images/{api,mobile}/Dockerfile` move with their pinning
discipline intact — the checksum-verified golangci-lint install and the
verification layer that fails the build when a toolchain does not match its pin
are both worth keeping. What changes is the base, the CA mechanism (§4a), and
the image name.

**Alpine wherever it works.** `ci-api` on Alpine is 298MB against roughly 1GB on
bookworm. Two notes on the port: `apk --print-arch` reports `x86_64`/`aarch64`
while golangci-lint's release assets use `amd64`/`arm64`, so the architecture
detection differs from the dpkg version; and if the API ever needs CGO, musl will
require `build-base` and yield musl-linked binaries.

**`ci-web` is the one image that cannot be Alpine.** Playwright's docs: *"Images
based on Alpine Linux are not supported due to differences in standard libraries
(musl vs. glibc)."* The browser binaries are glibc-linked. It is also rebased off
`node:*-slim`, which carries no browsers at all — installing Chromium and its
system libraries per run costs minutes on every job, and `cache.enabled: false`
means that cost is paid every time.

Mobile gets no runtime image — React Native emits an APK/IPA, not a container.

### Runtime images

| Image | Base | Notes |
|---|---|---|
| `shopper/api` | `gcr.io/distroless/static` | Multi-stage; static Go binary |
| `shopper/web` | `nginx:alpine` | Multi-stage; serves built `dist/` |

## 4a. The internal CA is fetched, never committed

Images must trust the step-ca root so `git clone https://gitea.homelab/...` and
internal HTTPS calls work. The certificate is **not** committed.

A root CA certificate is not secret — it is the public half, handed to every
client by design, and the sensitive `root_ca.key` is already a Docker secret. The
reasons to fetch it are different: a committed copy goes stale on rotation,
nobody diffs a `.crt` in review, and committing certs normalizes a habit that
eventually catches a private key.

**Mechanism.** Komodo's `pre_build` copies the live certificate into the build
context; the Dockerfile verifies it against `STEP_CA_FINGERPRINT` before
installing it. `.gitignore` keeps the staged file out of the repo.

The fingerprint is what makes an automated copy safe — it pins the CA's identity,
so a wrong or substituted file fails the build instead of producing an image that
trusts the wrong root. It is a SHA-256 over the **DER** encoding, matching
`step certificate fingerprint`; computing it over the PEM file bytes instead
would never match. Being a hash of a public certificate, committing *it* is
intended: short, self-verifying, reviewable in a diff.

**Why not fetch over the network.** Investigated and rejected: `stepca.homelab`
has no DNS record (NXDOMAIN from both a workstation and a node container — the
`.homelab` names are individual manual A records, no wildcard), and the overlay
`infra_public` is not attachable, so `docker build --network` is unavailable.
A network fetch would have needed a new DNS entry plus an NPM proxy exposing the
CA's management API to the LAN — real added surface to retrieve a certificate
that is already public.

Reading the file is also strictly more robust: `komodo-periphery` is `mode:
global` and already bind-mounts the authoritative file (`infra/compose.yaml:372`),
so it is present wherever a build lands, and a build cannot fail because step-ca
happens to be down.

**Bootstrap consequence.** The trigger workflow talks to `registry.homelab` and
`komodo.homelab`, both presenting step-ca certificates that a stock image cannot
verify. Using `-k` is not acceptable — those requests carry the registry password
and the Komodo API secret. So the workflow runs in `ci-api`, which makes the
first build manual: build and push `ci-api:1.0.0` by hand once, and every build
after that is automated.

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
       ├─ POST /write/UpdateBuild        ← declare version, image_name, image_tag
       ├─ POST /execute/RunBuild         ← returns immediately; keep the update id
       │    └─ Komodo clones, builds, pushes → registry.homelab/shopper/*
       ├─ POST /read/GetUpdate (poll)    ← until end_ts, then require success
       └─ registry HEAD manifest         ← assert the expected tag exists
```

Komodo's webhooks filter by branch only. A thin path-filtered workflow supplies
the missing filter and needs no Docker socket to do it — it only makes HTTP
calls.

**Two API calls rather than one webhook.** Komodo's `auto_increment_version`
defaults to `true`, which would make the tag unknown until after the build — so a
workflow could never reference a new image in the same commit that creates it.
Turning it off means the repo declares the version, which a bare webhook cannot
convey. `UpdateBuild` pins it; `RunBuild` starts it. This needs `KOMODO_API_KEY`
and `KOMODO_API_SECRET` as Gitea organisation secrets.

One Komodo Build resource per image:

```toml
git_provider = "gitea.homelab"
repo = "Homelab/shopper"
build_path = ".ci/api"
dockerfile_path = "Dockerfile"
image_registry = [{ domain = "registry.homelab", organization = "shopper" }]
build_args = "STEP_CA_FINGERPRINT=<fingerprint>"
pre_build = "cp /usr/local/share/ca-certificates/homelab-root-ca.crt .ci/api/homelab-root-ca.crt"
auto_increment_version = false   # default true
```

Tagging is **not** configured here. `UpdateBuild` sets `image_name`, `image_tag`
and the three `include_*` flags on every run, so the repo owns the published tag
and a UI edit cannot change what gets pushed. Only `image_registry` stays
UI-managed, because it names a stored credential.

### How Komodo composes `-t`, and the trap in it

`get_image_tags` emits tags from exactly four flags plus any additional tags, and
**nothing else** — there is no unconditional version tag:

| Flag | Emits |
|---|---|
| `image_tag` | `name:{image_tag}` — pure passthrough |
| `include_latest_tag` | `name:latest` |
| `include_version_tags` | `name:{version}` **and** `name:{major}.{minor}` **and** `name:{major}` |
| `include_commit_tag` | `name:{commit_hash}` |

`include_latest_tag` and `include_version_tags` publish **moving** tags —
`:latest`, `:1.2`, `:1` — which with `force_pull: false` are the silent-drift
hazard below. But `include_version_tags` is all-or-nothing: switching it off to
suppress `:1.2` and `:1` also removes the immutable `:1.2.3`, and with all four
unset the tag list is empty, so Komodo runs `docker build --push` with no `-t`
and the build dies on `tag is needed when pushing to registry`.

Setting `image_tag` to the declared version is the way out: one immutable tag,
no moving tags. (Cost us a build to learn — `--push` is only added when
`docker_login` *succeeded*, so a missing `-t` never indicates a registry
misconfiguration.)

`image_name` has a related trap: left empty, Komodo falls back to the **build
name**, publishing `shopper-ci-api` rather than `ci-api`.

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

Once Stage 1 is verified, `devflow/ci-images/` is deleted from homelab.

### Stage 1 status — 2026-07-30

| Item | State |
|---|---|
| Runner consolidation (3 → 1, `capacity: 5`, pinned `gitea/runner:2.3.0`) | **Done**, `2021133` |
| `shopper/.ci/api/Dockerfile` + `versions.env` + `.ci/README.md` | **Done**, `942abcf` |
| `.gitea/workflows/ci-images.yaml` | **Done**, `942abcf` |
| Komodo Build resource `shopper-ci-api` | Pending — needs Komodo UI/API access |
| Gitea org secrets (registry + Komodo pairs) | Pending — operator action |
| Bootstrap push of `ci-api:1.0.0` | Pending — needs registry credentials |
| Delete `devflow/ci-images/` | Pending — after end-to-end verification |

Verified locally against the live swarm: the image builds (298MB), a mismatched
`STEP_CA_FINGERPRINT` fails the build closed, and the resulting image completes
TLS to `https://gitea.homelab` without `-k`.

## 8. Error handling

| Failure | Surfaces as | Recovery |
|---|---|---|
| Tag already published | Trigger workflow fails with the bump instruction | Bump `versions.env` |
| Playwright version mismatch | CI job fails naming both versions | Bump `PLAYWRIGHT_VERSION`, rebuild `ci-web` |
| Registry auth failure | Pull fails in job container | Verify org-level Gitea secrets |
| Komodo build failure | Trigger workflow fails, printing Komodo's build log | Fix, bump `versions.env` |
| Build never finishes | Workflow fails at the poll deadline and cancels the build | Read Komodo build log |
| Pushed under the wrong name | Komodo reports success; the registry assertion fails | Fix `image_registry` |
| Komodo unreachable | `curl` fails the trigger job | Check Komodo Core health |
| CA rotated | Build fails naming expected vs actual fingerprint | Re-read it; bump `STEP_CA_FINGERPRINT` |

**The trigger waits for the outcome.** It was designed fire-and-forget, on the
reasoning that a failed build simply means the tag never appears and the guard
catches it next time. That was wrong in practice: it makes every failure look
like a pass and defers the news to whenever someone next pushes.

Polling is also not optional the way it first appeared. `RunBuild` spawns the
build and returns immediately, and the `Update` it returns is created *before*
the build runs, with `success: true` hardcoded by `make_update`. So the response
carries no outcome at all — any check against it reports every failure as
success. The result only exists once `finalize()` sets `success`, `end_ts` and
`status` together, which means re-reading the update by id.

Poll on `end_ts`, not `status`: `UpdateStatus` derives `Default` as `Complete`,
so status is the one field that can read "finished" on a record that never ran.

The registry assertion after that is a separate check, not belt-and-braces.
Komodo succeeding means its build command exited 0 — not that the tag this repo
expects exists.

## 9. Open items

- Whether Komodo pushes to `registry.homelab` via a stored account or an
  injected credential.
- The `noble` vs `jammy` suffix on the Playwright base tag, fixed at the moment
  the version is chosen.
- Whether `capacity: 5` holds on `vm-docker-adam`. Job containers are non-swarm
  siblings, so the runner service's `memory: 2G` limit does not bound them —
  five concurrent Playwright jobs are unbounded on the node. Worth watching
  before raising further, per the existing note in the runner config.
- Whether the trigger workflow should move to a purpose-built `ci-tools` image
  rather than `ci-api`. It needs only curl, jq and the internal CA; using
  `ci-api` pulls a Go toolchain to make four HTTP calls. Not worth a second
  bootstrap today, but revisit if the trigger grows.
- `gitea/gitea:1` in `devflow/compose.yaml` still floats on a major tag, unlike
  the runner which is now pinned exactly. Out of scope here; worth a decision.

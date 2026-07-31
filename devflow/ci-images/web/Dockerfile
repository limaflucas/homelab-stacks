# CI job image — React web.
#
# Selected by `runs-on: homelab-web`. Every toolchain is pinned: an agent that
# passes tests today must pass them tomorrow for the same commit, so nothing
# here may float on `latest`.
#
# Build from the ci-images/ directory so that shared/ is in context:
#   docker build -f web/Dockerfile -t registry.homelab/homelab/devflow-ci-web:<tag> .

ARG NODE_VERSION=22.23.2
FROM node:${NODE_VERSION}-bookworm-slim

# Re-declared after FROM on purpose. An ARG above FROM is only in scope for the
# FROM line itself. The node image also exports its own NODE_VERSION env var, so
# omitting this leaves the check below validating the base image against itself
# instead of against this pin.
ARG NODE_VERSION
ARG PNPM_VERSION=11.18.0

ENV TZ=America/Halifax \
    DEBIAN_FRONTEND=noninteractive \
    # Keep the store inside the image layer cache rather than $HOME, so a job
    # container that mounts over /root still finds it.
    PNPM_HOME=/usr/local/share/pnpm \
    CI=true
ENV PATH="${PNPM_HOME}:${PATH}"

# The slim image ships neither git nor curl, and `actions/checkout` needs git.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl ca-certificates jq unzip \
 && rm -rf /var/lib/apt/lists/*

# Trust the internal step-ca root so `git clone https://gitea.homelab/...` and
# any internal HTTPS fetch work. Node does not read the system pool by default,
# so NODE_EXTRA_CA_CERTS points it at the same file.
COPY shared/homelab-root-ca.crt /usr/local/share/ca-certificates/homelab-root-ca.crt
RUN update-ca-certificates
ENV NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/homelab-root-ca.crt

# Pin the package manager itself. Corepack otherwise resolves a version from
# each repo's packageManager field at first invocation, which makes the image's
# behaviour depend on the checkout rather than on this tag.
RUN set -eux; \
    corepack enable; \
    corepack prepare "pnpm@${PNPM_VERSION}" --activate; \
    pnpm --version

# Fail the build rather than shipping an image whose toolchain does not match
# the pin. A silently-wrong image produces confusing CI results much later.
RUN set -eux; \
    node --version | grep -qx "v${NODE_VERSION}"; \
    pnpm --version | grep -qx "${PNPM_VERSION}"; \
    git --version; curl --version | head -1; jq --version

WORKDIR /workspace

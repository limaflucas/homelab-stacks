# CI job image — React Native (JS only).
#
# Selected by `runs-on: homelab-mobile`. Covers lint, typecheck, Jest and a
# Metro bundle. It deliberately does **not** carry a JDK or the Android SDK, so
# `assembleDebug` will not run here, and iOS cannot be built on Linux at all.
# Device and simulator verification stays manual at Gate 3 — that gap is
# recorded in the spec, not accidentally left open.
#
# Contents are currently near-identical to the web image. It is a separate image
# on purpose: React Native's supported Node range trails the web ecosystem's, so
# this pin must be able to move independently of web's without a coupled rebuild.
#
# Build from the ci-images/ directory so that shared/ is in context:
#   docker build -f mobile/Dockerfile -t registry.homelab/homelab/devflow-ci-mobile:<tag> .

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
    PNPM_HOME=/usr/local/share/pnpm \
    CI=true
ENV PATH="${PNPM_HOME}:${PATH}"

# git for actions/checkout. watchman is intentionally absent: Metro only needs
# it for filesystem watching in interactive development, never in a one-shot CI
# bundle, and it is an expensive build from source on Debian.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl ca-certificates jq unzip \
 && rm -rf /var/lib/apt/lists/*

COPY shared/homelab-root-ca.crt /usr/local/share/ca-certificates/homelab-root-ca.crt
RUN update-ca-certificates
ENV NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/homelab-root-ca.crt

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

ARG NODE_VERSION=22.23.2
FROM node:${NODE_VERSION}-bookworm-slim

ARG NODE_VERSION
ARG PNPM_VERSION=11.18.0

ENV TZ=America/Halifax \
    DEBIAN_FRONTEND=noninteractive \
    PNPM_HOME=/usr/local/share/pnpm \
    CI=true
ENV PATH="${PNPM_HOME}:${PATH}"

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

RUN set -eux; \
    node --version | grep -qx "v${NODE_VERSION}"; \
    pnpm --version | grep -qx "${PNPM_VERSION}"; \
    git --version; curl --version | head -1; jq --version

WORKDIR /workspace

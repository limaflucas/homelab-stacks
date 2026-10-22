ARG GO_VERSION=1.26.5
FROM golang:${GO_VERSION}-bookworm

ARG GO_VERSION
ARG GOLANGCI_LINT_VERSION=2.12.2

ENV TZ=America/Halifax \
    DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local

RUN apt-get update \
 && apt-get install -y --no-install-recommends jq unzip \
 && rm -rf /var/lib/apt/lists/*

COPY shared/homelab-root-ca.crt /usr/local/share/ca-certificates/homelab-root-ca.crt
RUN update-ca-certificates

RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    base="https://github.com/golangci/golangci-lint/releases/download/v${GOLANGCI_LINT_VERSION}"; \
    tarball="golangci-lint-${GOLANGCI_LINT_VERSION}-linux-${arch}.tar.gz"; \
    curl -sSfL "${base}/${tarball}" -o /tmp/gcl.tar.gz; \
    curl -sSfL "${base}/golangci-lint-${GOLANGCI_LINT_VERSION}-checksums.txt" -o /tmp/gcl-sums.txt; \
    expected="$(awk -v f="$tarball" '$2==f {print $1}' /tmp/gcl-sums.txt)"; \
    test -n "$expected"; \
    echo "${expected}  /tmp/gcl.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/gcl.tar.gz -C /tmp; \
    mv "/tmp/golangci-lint-${GOLANGCI_LINT_VERSION}-linux-${arch}/golangci-lint" /usr/local/bin/; \
    rm -rf /tmp/gcl.tar.gz /tmp/gcl-sums.txt "/tmp/golangci-lint-${GOLANGCI_LINT_VERSION}-linux-${arch}"; \
    golangci-lint --version

RUN set -eux; \
    go version | grep -q "go${GO_VERSION} " ; \
    git --version; curl --version | head -1; jq --version

WORKDIR /workspace

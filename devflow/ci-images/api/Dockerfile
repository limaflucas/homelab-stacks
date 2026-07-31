# CI job image — Go API.
#
# Selected by `runs-on: homelab-api`. Every toolchain is pinned: an agent that
# passes tests today must pass them tomorrow for the same commit, so nothing
# here may float on `latest`.
#
# Build from the ci-images/ directory so that shared/ is in context:
#   docker build -f api/Dockerfile -t registry.homelab/homelab/devflow-ci-api:<tag> .

ARG GO_VERSION=1.26.5
FROM golang:${GO_VERSION}-bookworm

# Re-declared after FROM on purpose. An ARG above FROM is only in scope for the
# FROM line itself, so without this the verification step below would expand an
# empty string and silently check nothing.
ARG GO_VERSION
ARG GOLANGCI_LINT_VERSION=2.12.2

ENV TZ=America/Halifax \
    DEBIAN_FRONTEND=noninteractive \
    # Refuse to silently download a different toolchain when a go.mod names one.
    # Without this, `go build` fetches its own Go and the pin above becomes a
    # suggestion rather than a guarantee.
    GOTOOLCHAIN=local

# The golang image already carries git, curl and ca-certificates. jq is here
# because workflows parse API responses; unzip because some actions ship zips.
RUN apt-get update \
 && apt-get install -y --no-install-recommends jq unzip \
 && rm -rf /var/lib/apt/lists/*

# Trust the internal step-ca root so that `git clone https://gitea.homelab/...`
# and `go mod download` against internal hosts work. Go on Linux reads the
# system pool, so this one store covers both.
COPY shared/homelab-root-ca.crt /usr/local/share/ca-certificates/homelab-root-ca.crt
RUN update-ca-certificates

# Checksum-verified install: the release archive is pinned by version *and*
# validated against the upstream checksums file, so a retagged release cannot
# change what lands in this image.
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    base="https://github.com/golangci/golangci-lint/releases/download/v${GOLANGCI_LINT_VERSION}"; \
    tarball="golangci-lint-${GOLANGCI_LINT_VERSION}-linux-${arch}.tar.gz"; \
    curl -sSfL "${base}/${tarball}" -o /tmp/gcl.tar.gz; \
    curl -sSfL "${base}/golangci-lint-${GOLANGCI_LINT_VERSION}-checksums.txt" -o /tmp/gcl-sums.txt; \
    # Recompose the checksum line rather than rewriting it in place: upstream
    # separates hash and filename with two spaces, and any edit that changes
    # that spacing makes sha256sum look for a filename with a leading space.
    expected="$(awk -v f="$tarball" '$2==f {print $1}' /tmp/gcl-sums.txt)"; \
    test -n "$expected"; \
    echo "${expected}  /tmp/gcl.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/gcl.tar.gz -C /tmp; \
    mv "/tmp/golangci-lint-${GOLANGCI_LINT_VERSION}-linux-${arch}/golangci-lint" /usr/local/bin/; \
    rm -rf /tmp/gcl.tar.gz /tmp/gcl-sums.txt "/tmp/golangci-lint-${GOLANGCI_LINT_VERSION}-linux-${arch}"; \
    golangci-lint --version

# Fail the build rather than shipping an image whose toolchain does not match
# the pin. A silently-wrong image produces confusing CI results much later.
RUN set -eux; \
    go version | grep -q "go${GO_VERSION} " ; \
    git --version; curl --version | head -1; jq --version

WORKDIR /workspace

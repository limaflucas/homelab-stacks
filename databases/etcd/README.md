# etcd

This directory contains the configuration for a distributed key-value store (etcd), optimized for Docker Swarm. It serves as the Distributed Configuration Store (DCS) for the homelab's high-availability services.

## Goal

To provide a highly available and consistent key-value store for service discovery and cluster coordination, specifically for the PostgreSQL HA setup.

## Architecture

- **Mode:** Clustered
- **Image:** `public.ecr.aws/bitnami/etcd:3`
- **Deployment:** Global mode, constrained to manager nodes.
- **Nodes:**
  - `etcd-vm-docker-adam`
  - `etcd-vm-docker-zeus`
  - `etcd-vm-docker-bragi`
- **Persistence:** 
  - Data: `/opt/docker-data/databases/etcd/data`
- **Network:** Connected to the `databases` external overlay network.

## Prerequisites

### 1. External Network
Ensure the `databases` network exists:
```bash
docker network create --driver overlay databases
```

### 2. Storage
Ensure the data directory exists on all manager nodes:
```bash
sudo mkdir -p /opt/docker-data/databases/etcd/data
sudo chown -R 1001:1001 /opt/docker-data/databases/etcd/data
```

## Deployment

Deploy the stack:
```bash
docker stack deploy -c compose.yaml databases
```

## Verification

### Check Cluster Health
```bash
docker exec -it $(docker ps -q -f name=databases_etcd) etcdctl endpoint health
```

### Check Cluster Membership
```bash
docker exec -it $(docker ps -q -f name=databases_etcd) etcdctl member list
```

## Usage

Services requiring a DCS can connect using the client URLs:
`http://etcd-vm-docker-adam:2379,http://etcd-vm-docker-zeus:2379,http://etcd-vm-docker-bragi:2379`

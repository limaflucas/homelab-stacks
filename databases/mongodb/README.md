# MongoDB

This directory contains the configuration for a shared MongoDB replica set, optimized for Docker Swarm.

## Goal

To provide a centralized, highly available NoSQL database backend for the homelab environment.

## Architecture

- **Mode:** Replica Set (`rs0`)
- **Nodes:** 3 replicas, distributed across the Swarm (enforced by `max_replicas_per_node: 1`).
- **Persistence:** Bound to `/opt/docker-data/databases/mongodb/` on each node.
- **Network:** Connected to the `databases` overlay network.

## Installation Steps

1.  **Create the external secrets:**
    ```bash
    # Root credentials
    echo "root_user" | docker secret create mongodb_user -
    echo "your_secure_db_password" | docker secret create mongodb_password -

    # Security Keyfile (must be the same across all nodes)
    openssl rand -base64 756 | docker secret create mongodb_keyfile -
    ```

2.  **Deploy the stack:**
    ```bash
    docker stack deploy -c compose.yaml databases
    ```

3.  **Initiate the Replica Set:**
    Wait for the services to be running, then execute the following command to initiate the replica set. Replace the hostnames with your actual node addresses.

    ```bash
    # Initiate the replica set from any node running a MongoDB replica
    # (The following command automatically retrieves credentials from the container's secrets)
    docker exec -it $(docker ps -q -f name=databases_mongodb.1) mongosh \
      --username $(docker exec $(docker ps -q -f name=databases_mongodb.1) cat /run/secrets/mongodb_user) \
      --password $(docker exec $(docker ps -q -f name=databases_mongodb.1) cat /run/secrets/mongodb_password)

    # Run initiation command
    rs.initiate({
      _id: "rs0",
      members: [
        { _id: 0, host: "adam.homelab:27017",  priority: 1 },
        { _id: 1, host: "zeus.homelab:27017", priority: 2 }, // preferred PRIMARY
        { _id: 2, host: "bragi.homelab:27017", priority: 1 },
      ]
    })
    ```

## Usage

Other services can connect using the following connection string pattern:
`mongodb://<user>:<password>@mongodb-node1:27017,mongodb-node2:27017,mongodb-node3:27017/?replicaSet=rs0`

*Note: In Swarm, you can also use the service name `mongodb` if using the overlay network, but for replica sets, explicit member discovery is often preferred.*

## Configuration Details

- **Image:** `mongo:7.0`
- **Memory Cache:** Limited to 0.25GB WiredTiger cache.
- **Resources:** Limited to 0.5 CPU and 1GB RAM per node.
- **Ports:** Published in `host` mode on 27017.

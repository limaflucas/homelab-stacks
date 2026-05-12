# MongoDB

This directory contains the configuration for a shared MongoDB replica set, optimized for Docker Swarm.

## Goal

To provide a centralized, highly available NoSQL database backend for the homelab environment.

## Architecture

- **Mode:** Replica Set (`rs0`)
- **Nodes:** 3 replicas, distributed across the Swarm (enforced by `max_replicas_per_node: 1`).
- **Hostname:** Dynamically assigned using `mongodb-{{.Node.Hostname}}`.
- **Persistence:** 
  - Data: `/opt/docker-data/databases/mongodb/data`
  - Config: `/opt/docker-data/databases/mongodb/config`
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
    Wait for the services to be running, then execute the following command to initiate the replica set. Use the dynamic hostnames assigned to your nodes.

    ```bash
    # Exec into one of the running containers
    docker exec -it $(docker ps -q -f name=databases_mongodb) mongosh \
      --username $(cat /run/secrets/mongodb_user) \
      --password $(cat /run/secrets/mongodb_password)

    # Run initiation command (replace <node-hostname> with actual hostnames)
    rs.initiate({
      _id: "rs0",
      members: [
        { _id: 0, host: "mongodb-<node1-hostname>:27017", priority: 2 },
        { _id: 1, host: "mongodb-<node2-hostname>:27017", priority: 1 },
        { _id: 2, host: "mongodb-<node3-hostname>:27017", priority: 1 },
      ]
    })
    ```

## Usage

Other services can connect using the following connection string pattern:
`mongodb://<user>:<password>@mongodb-<node1>:27017,mongodb-<node2>:27017,mongodb-<node3>:27017/?replicaSet=rs0`

## Configuration Details

- **Image:** `mongo:8`
- **Memory Cache:** Limited to 0.25GB WiredTiger cache.
- **Resources:** Limited to 0.5 CPU and 512M RAM per node.
- **Ports:** Published in `host` mode on 27017.
- **Security:** Authenticated access with mandatory keyfile for replica set communication.

# MinIO

This directory contains the configuration for a standalone MinIO service, an S3-compatible object storage server.

## Architecture

- **Mode:** Standalone (Single-Node, Single-Drive)
- **Image:** `minio/minio:latest`
- **Networking:** Connected to the `databases` overlay network.
- **Persistence:** Data is stored on the host at `/opt/docker-data/databases/minio/data`.

## Installation Steps

1.  **Create the external secrets:**
    ```bash
    echo "your_secure_admin_user" | docker secret create minio_root_user -
    echo "your_secure_admin_password" | docker secret create minio_root_password -
    ```

2.  **Deploy the stack:**
    ```bash
    docker stack deploy -c compose.yaml databases
    ```

## Configuration Details
- **Ports:** API is available internally on 9000, Console on 9001.
- **Resources:** Limited to 0.5 CPU and 512M RAM.

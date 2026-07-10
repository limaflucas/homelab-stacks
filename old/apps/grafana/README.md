# Apps: Grafana

This directory contains the configuration for the monitoring and observability stack.

## Tools Configured

*   **Grafana**: A multi-platform open source analytics and interactive visualization web application.
*   **VictoriaMetrics**: A fast, cost-effective and scalable time series database and monitoring solution.
*   **VictoriaLogs**: An open source user-friendly database for logs.
*   **Grafana Alloy**: A vendor-neutral programmable telemetry collector.

## Goal

To collect, store, and visualize metrics and logs from the host system and running containers to ensure system health and observability.

## Usage in this Project

*   **Alloy** is configured to collect system metrics, Docker container metrics, and logs.
*   The collected data is sent to **VictoriaMetrics** (for time-series data) and **VictoriaLogs** (for log data) for long-term storage (7-day retention configured).
*   **Grafana** is used to query and visualize this data, pre-configured with the VictoriaMetrics/VictoriaLogs data source plugins. It is accessible on port `3000`.

## Installation Steps

2.  Navigate to this directory:
    ```bash
    cd apps/grafana
    ```
2.  Review and customize `config.alloy` and files in `provisioning/` if necessary.
3.  Start the stack:
    ```bash
    docker compose up -d
    ```
4.  Access Grafana at `http://<your-server-ip>:3000`.

#!/bin/bash
set -e

# Create databases and users for Outline and Vaultwarden
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER outline WITH PASSWORD '$POSTGRES_PASSWORD';
    CREATE DATABASE outline;
    GRANT ALL PRIVILEGES ON DATABASE outline TO outline;

    CREATE USER vaultwarden WITH PASSWORD '$POSTGRES_PASSWORD';
    CREATE DATABASE vaultwarden;
    GRANT ALL PRIVILEGES ON DATABASE vaultwarden TO vaultwarden;
EOSQL

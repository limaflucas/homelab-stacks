#!/bin/bash
set -e

REPLICATOR_PASSWORD=$(cat /run/secrets/postgresql_replication_password)
PGPOOL_PASSWORD=$(cat /run/secrets/pgpool_admin_password)

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" << EOSQL

-- Replication user
CREATE USER replicator WITH REPLICATION LOGIN PASSWORD '${REPLICATOR_PASSWORD}';

-- pgpool health check user
CREATE USER pgpool WITH PASSWORD '${PGPOOL_PASSWORD}' LOGIN;
GRANT pg_monitor TO pgpool;

-- Application users and databases
CREATE USER npm WITH PASSWORD 'change_me' LOGIN;
CREATE DATABASE npm OWNER npm;

CREATE USER outline WITH PASSWORD 'change_me' LOGIN;
CREATE DATABASE outline OWNER outline;

CREATE USER vaultwarden WITH PASSWORD 'change_me' LOGIN;
CREATE DATABASE vaultwarden OWNER vaultwarden;

EOSQL
#!/usr/bin/env bash
set -e

# Clean up variables by removing any single quotes passed from the .env file
CLEAN_USER="${GEOSTORE_DB_USER//\'/}"
CLEAN_PASS="${GEOSTORE_DB_PASS//\'/}"
CLEAN_SCHEMA="${GEOSTORE_DB_SCHEMA//\'/}"
CLEAN_ROOT_PASS="${POSTGRES_PASSWORD//\'/}"

psql -v ON_ERROR_STOP=1 --username postgres --dbname "$POSTGRES_DB" <<-EOSQL
    ALTER USER postgres WITH PASSWORD '${CLEAN_ROOT_PASS}';
    CREATE USER "${CLEAN_USER}" LOGIN PASSWORD '${CLEAN_PASS}' NOSUPERUSER INHERIT NOCREATEDB NOCREATEROLE;
    CREATE SCHEMA "${CLEAN_SCHEMA}";
    GRANT USAGE ON SCHEMA "${CLEAN_SCHEMA}" TO "${CLEAN_USER}";
    GRANT ALL ON SCHEMA "${CLEAN_SCHEMA}" TO "${CLEAN_USER}";
    ALTER USER "${CLEAN_USER}" SET search_path TO "${CLEAN_SCHEMA}", public;

    CREATE USER geostore_test LOGIN PASSWORD 'geostore_test' NOSUPERUSER INHERIT NOCREATEDB NOCREATEROLE;
    CREATE SCHEMA geostore_test;
    GRANT USAGE ON SCHEMA geostore_test TO geostore_test;
    GRANT ALL ON SCHEMA geostore_test TO geostore_test;
    ALTER USER geostore_test SET search_path TO geostore_test, public;
EOSQL

# Execute the external schema injection cleanly using the sanitized password
PGPASSWORD="${CLEAN_PASS}" PGOPTIONS="--search_path=${CLEAN_SCHEMA}" psql -v ON_ERROR_STOP=1 --username "${CLEAN_USER}" --dbname "$POSTGRES_DB" < /code/002_create_schema_postgres.sql

echo "✓ Inicialización completada: GeoStore schema creado correctamente"

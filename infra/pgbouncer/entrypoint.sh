#!/bin/sh
set -eu

read_secret() {
  name="$1"
  file_var="${name}_FILE"
  file_value=$(eval "printf '%s' \"\${$file_var:-}\"")
  value=$(eval "printf '%s' \"\${$name:-}\"")
  if [ -n "$value" ]; then
    printf '%s' "$value"
  elif [ -n "$file_value" ]; then
    cat "$file_value"
  fi
}

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${APP_DB_USER:=app_user}"
: "${MIGRATION_DB_USER:=migration_user}"
: "${CITUS_COORDINATOR_HOST:=citus_coordinator}"
: "${PGBOUNCER_MAX_CLIENT_CONN:=500}"
: "${PGBOUNCER_DEFAULT_POOL_SIZE:=20}"
: "${PGBOUNCER_RESERVE_POOL_SIZE:=5}"
: "${PGBOUNCER_CLIENT_TLS_SSLMODE:=verify-ca}"
: "${PGBOUNCER_SERVER_TLS_SSLMODE:=verify-full}"

POSTGRES_PASSWORD="$(read_secret POSTGRES_PASSWORD)"
APP_DB_PASSWORD="$(read_secret APP_DB_PASSWORD)"
MIGRATION_DB_PASSWORD="$(read_secret MIGRATION_DB_PASSWORD)"

if [ -z "$POSTGRES_PASSWORD" ] || [ -z "$APP_DB_PASSWORD" ] || [ -z "$MIGRATION_DB_PASSWORD" ]; then
  echo "POSTGRES/APP/MIGRATION database passwords are required" >&2
  exit 1
fi

install -d -m 0700 -o pgbouncer -g pgbouncer /var/lib/pgbouncer/tls
if [ "${PGBOUNCER_CLIENT_TLS_SSLMODE}" != "disable" ] || [ "${PGBOUNCER_SERVER_TLS_SSLMODE}" != "disable" ]; then
  cp /certs/ca.crt /var/lib/pgbouncer/tls/ca.crt
  cp /certs/pgbouncer_server.crt /var/lib/pgbouncer/tls/pgbouncer_server.crt
  cp /certs/pgbouncer_server.key /var/lib/pgbouncer/tls/pgbouncer_server.key
  cp /certs/pgbouncer_client.crt /var/lib/pgbouncer/tls/pgbouncer_client.crt
  cp /certs/pgbouncer_client.key /var/lib/pgbouncer/tls/pgbouncer_client.key
  chown -R pgbouncer:pgbouncer /var/lib/pgbouncer/tls
  chmod 0644 /var/lib/pgbouncer/tls/*.crt
  chmod 0600 /var/lib/pgbouncer/tls/*.key
fi

export POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD APP_DB_USER MIGRATION_DB_USER CITUS_COORDINATOR_HOST \
  PGBOUNCER_MAX_CLIENT_CONN PGBOUNCER_DEFAULT_POOL_SIZE PGBOUNCER_RESERVE_POOL_SIZE \
  PGBOUNCER_CLIENT_TLS_SSLMODE PGBOUNCER_SERVER_TLS_SSLMODE

{
  echo "[databases]"
  echo "${POSTGRES_DB} = host=${CITUS_COORDINATOR_HOST} port=5432 dbname=${POSTGRES_DB}"
  echo
  envsubst < /usr/local/share/pgbouncer/pgbouncer.ini.template
} > /etc/pgbouncer/pgbouncer.ini

{
  printf '"%s" "%s"\n' "$POSTGRES_USER" "$POSTGRES_PASSWORD"
  printf '"%s" "%s"\n' "$APP_DB_USER" "$APP_DB_PASSWORD"
  printf '"%s" "%s"\n' "$MIGRATION_DB_USER" "$MIGRATION_DB_PASSWORD"
} > /etc/pgbouncer/userlist.txt

chown pgbouncer:pgbouncer /etc/pgbouncer/pgbouncer.ini /etc/pgbouncer/userlist.txt
chmod 0600 /etc/pgbouncer/userlist.txt
exec su-exec pgbouncer pgbouncer /etc/pgbouncer/pgbouncer.ini

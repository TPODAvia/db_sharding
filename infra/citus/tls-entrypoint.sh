#!/usr/bin/env bash
set -euo pipefail

if [[ "${POSTGRES_SSL:-on}" == "on" ]]; then
  mkdir -p /var/lib/postgresql/tls

  cp /certs/postgres_server.crt /var/lib/postgresql/tls/server.crt
  cp /certs/postgres_server.key /var/lib/postgresql/tls/server.key
  cp /certs/ca.crt /var/lib/postgresql/tls/ca.crt

  chmod 0700 /var/lib/postgresql/tls
  chmod 0644 /var/lib/postgresql/tls/server.crt /var/lib/postgresql/tls/ca.crt
  chmod 0600 /var/lib/postgresql/tls/server.key

  chown -R postgres:postgres /var/lib/postgresql/tls
fi

exec docker-entrypoint.sh "$@"

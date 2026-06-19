#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env

COMPOSE_FILES=(-f docker-compose.yml)
if [[ -f docker-compose.workers.yml ]]; then
  COMPOSE_FILES+=(-f docker-compose.workers.yml)
fi

POSTGRES_USER="${POSTGRES_USER:-gr5}"
POSTGRES_DB="${POSTGRES_DB:-gr5}"

echo "Bootstrapping DB roles on citus_coordinator"
docker compose "${COMPOSE_FILES[@]}" exec -T citus_coordinator bash /docker-entrypoint-initdb.d/002_roles.sh
docker compose "${COMPOSE_FILES[@]}" exec -T citus_coordinator \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "SELECT rolname FROM pg_roles WHERE rolname IN ('${APP_DB_USER:-app_user}', '${MIGRATION_DB_USER:-migration_user}', '${READONLY_DB_USER:-readonly_user}', '${MONITORING_DB_USER:-monitoring_user}', '${BACKUP_DB_USER:-backup_user}') ORDER BY rolname;"

for service in $(seq -f 'citus_worker%.0f' 1 "${CITUS_WORKER_COUNT:-2}"); do
  echo "Checking DB roles on ${service}"
  docker compose "${COMPOSE_FILES[@]}" exec -T "$service" \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "SELECT rolname FROM pg_roles WHERE rolname IN ('${APP_DB_USER:-app_user}', '${MIGRATION_DB_USER:-migration_user}', '${READONLY_DB_USER:-readonly_user}', '${MONITORING_DB_USER:-monitoring_user}', '${BACKUP_DB_USER:-backup_user}') ORDER BY rolname;"
done

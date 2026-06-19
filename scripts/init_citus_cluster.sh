#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env

WORKERS="${1:-${CITUS_WORKER_COUNT:-2}}"
COMPOSE_FILES=(-f docker-compose.yml)

./scripts/init_secrets.sh
./scripts/init_tls_certs.sh
python3 scripts/render_citus_workers_compose.py "$WORKERS"
COMPOSE_FILES+=(-f docker-compose.workers.yml)

docker compose "${COMPOSE_FILES[@]}" up -d citus_coordinator
for i in $(seq 1 "$WORKERS"); do
  docker compose "${COMPOSE_FILES[@]}" up -d "citus_worker${i}"
done

echo "waiting for Citus coordinator/workers..."
docker compose "${COMPOSE_FILES[@]}" exec -T citus_coordinator bash -lc 'until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do sleep 1; done'
for i in $(seq 1 "$WORKERS"); do
  docker compose "${COMPOSE_FILES[@]}" exec -T "citus_worker${i}" bash -lc 'until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do sleep 1; done'
done

POSTGRES_PASSWORD="$(cat docker/secrets/postgres_password.txt)"
APP_DB_PASSWORD="$(cat docker/secrets/app_db_password.txt)"
MIGRATION_DB_PASSWORD="$(cat docker/secrets/migration_db_password.txt)"
READONLY_DB_PASSWORD="$(cat docker/secrets/readonly_db_password.txt)"
MONITORING_DB_PASSWORD="$(cat docker/secrets/monitoring_db_password.txt)"
BACKUP_DB_PASSWORD="$(cat docker/secrets/backup_db_password.txt)"

echo "Configuring pgpass for Citus inter-node connections..."
for service in citus_coordinator $(seq -f 'citus_worker%.0f' 1 "$WORKERS"); do
  {
    for host in citus_coordinator $(seq -f 'citus_worker%.0f' 1 "$WORKERS"); do
      echo "${host}:5432:*:${POSTGRES_USER:-gr5}:${POSTGRES_PASSWORD}"
      echo "${host}:5432:*:${APP_DB_USER:-app_user}:${APP_DB_PASSWORD}"
      echo "${host}:5432:*:${MIGRATION_DB_USER:-migration_user}:${MIGRATION_DB_PASSWORD}"
      echo "${host}:5432:*:${READONLY_DB_USER:-readonly_user}:${READONLY_DB_PASSWORD}"
      echo "${host}:5432:*:${MONITORING_DB_USER:-monitoring_user}:${MONITORING_DB_PASSWORD}"
      echo "${host}:5432:*:${BACKUP_DB_USER:-backup_user}:${BACKUP_DB_PASSWORD}"
    done
  } | docker compose "${COMPOSE_FILES[@]}" exec -T "$service" bash -lc '
    cat > /var/lib/postgresql/.pgpass
    chmod 0600 /var/lib/postgresql/.pgpass
    chown postgres:postgres /var/lib/postgresql/.pgpass
  '
done

export CITUS_WORKER_COUNT="$WORKERS"
./scripts/init_db_roles.sh

echo "registering workers..."
for i in $(seq 1 "$WORKERS"); do
  docker compose "${COMPOSE_FILES[@]}" exec -T -e PGPASSWORD="${POSTGRES_PASSWORD}" citus_coordinator psql -U "${POSTGRES_USER:-gr5}" -d "${POSTGRES_DB:-gr5}" -v ON_ERROR_STOP=1 <<SQL
CREATE EXTENSION IF NOT EXISTS citus;
SELECT * FROM citus_add_node('citus_worker${i}', 5432)
WHERE NOT EXISTS (
  SELECT 1 FROM citus_get_active_worker_nodes() WHERE node_name = 'citus_worker${i}' AND node_port = 5432
);
SQL
done

echo "active workers:"
docker compose "${COMPOSE_FILES[@]}" exec -T -e PGPASSWORD="${POSTGRES_PASSWORD}" citus_coordinator psql -U "${POSTGRES_USER:-gr5}" -d "${POSTGRES_DB:-gr5}" -c "SELECT * FROM citus_get_active_worker_nodes();"

docker compose "${COMPOSE_FILES[@]}" up -d pgbouncer

echo "Rebuilding writer_service before Alembic migrations..."
docker compose "${COMPOSE_FILES[@]}" build writer_service

./scripts/migrate_db_direct.sh

docker compose "${COMPOSE_FILES[@]}" exec -T -e PGPASSWORD="${POSTGRES_PASSWORD}" citus_coordinator psql -U "${POSTGRES_USER:-gr5}" -d "${POSTGRES_DB:-gr5}" -v ON_ERROR_STOP=1 <<'SQL'
SELECT logicalrelid::regclass AS table_name, partmethod, partkey FROM pg_dist_partition;
SELECT count(*) AS shard_count FROM pg_dist_shard;
SQL

docker compose "${COMPOSE_FILES[@]}" up -d writer_service reader_service

echo "Citus cluster is initialized."

#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env

WORKERS="${1:-${CITUS_WORKER_COUNT:-2}}"
COMPOSE_FILES=(-f docker-compose.yml)

./scripts/init_secrets.sh
./scripts/init_tls_certs.sh
python scripts/render_citus_workers_compose.py "$WORKERS"
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

./scripts/init_db_roles.sh

echo "registering workers..."
for i in $(seq 1 "$WORKERS"); do
  docker compose "${COMPOSE_FILES[@]}" exec -T citus_coordinator psql -U "${POSTGRES_USER:-gr5}" -d "${POSTGRES_DB:-gr5}" -v ON_ERROR_STOP=1 <<SQL
CREATE EXTENSION IF NOT EXISTS citus;
SELECT * FROM citus_add_node('citus_worker${i}', 5432)
WHERE NOT EXISTS (
  SELECT 1 FROM citus_get_active_worker_nodes() WHERE node_name = 'citus_worker${i}' AND node_port = 5432
);
SQL
done

echo "active workers:"
docker compose "${COMPOSE_FILES[@]}" exec -T citus_coordinator psql -U "${POSTGRES_USER:-gr5}" -d "${POSTGRES_DB:-gr5}" -c "SELECT * FROM citus_get_active_worker_nodes();"

docker compose "${COMPOSE_FILES[@]}" up -d pgbouncer
./scripts/migrate_db_direct.sh

docker compose "${COMPOSE_FILES[@]}" exec -T citus_coordinator psql -U "${POSTGRES_USER:-gr5}" -d "${POSTGRES_DB:-gr5}" -v ON_ERROR_STOP=1 <<'SQL'
SELECT logicalrelid::regclass AS table_name, partmethod, partkey FROM pg_dist_partition;
SELECT count(*) AS shard_count FROM pg_dist_shard;
SQL

docker compose "${COMPOSE_FILES[@]}" up -d writer_service reader_service

echo "Citus cluster is initialized."

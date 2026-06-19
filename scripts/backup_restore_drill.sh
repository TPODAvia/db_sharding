#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env

BACKUP_DIR="${1:?Usage: $0 <backup_dir_from_backup_all_shards.sh>}"
DUMP_FILE="${BACKUP_DIR}/coordinator.dump"
[ -f "$DUMP_FILE" ] || { echo "Dump file not found: ${DUMP_FILE}" >&2; exit 1; }

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.workers.yml"
POSTGRES_USER="${POSTGRES_USER:-$(grep -E '^POSTGRES_USER=' .env 2>/dev/null | tail -1 | cut -d= -f2 || echo gr5)}"
POSTGRES_DB="${POSTGRES_DB:-$(grep -E '^POSTGRES_DB=' .env 2>/dev/null | tail -1 | cut -d= -f2 || echo gr5)}"
DRILL_DB="${RESTORE_DRILL_DB:-restore_drill_$(date -u +%Y%m%d%H%M%S)}"

./scripts/verify_backup.sh "$BACKUP_DIR"

echo "Creating temporary restore drill database: ${DRILL_DB}"
$COMPOSE exec -T citus_coordinator createdb -U "$POSTGRES_USER" "$DRILL_DB"
cleanup() {
  echo "Dropping temporary restore drill database: ${DRILL_DB}"
  $COMPOSE exec -T citus_coordinator dropdb -U "$POSTGRES_USER" --if-exists "$DRILL_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT

$COMPOSE exec -T citus_coordinator psql -U "$POSTGRES_USER" -d "$DRILL_DB" -v ON_ERROR_STOP=1 <<SQL
CREATE EXTENSION IF NOT EXISTS citus;
SQL

for i in $(seq 1 "${CITUS_WORKER_COUNT:-2}"); do
  $COMPOSE exec -T citus_coordinator psql -U "$POSTGRES_USER" -d "$DRILL_DB" -v ON_ERROR_STOP=1 <<SQL
SELECT citus_add_node('citus_worker${i}', 5432)
WHERE NOT EXISTS (
  SELECT 1 FROM pg_dist_node WHERE nodename = 'citus_worker${i}' AND nodeport = 5432
);
SQL
done

cat "$DUMP_FILE" | $COMPOSE exec -T citus_coordinator pg_restore \
  -U "$POSTGRES_USER" \
  -d "$DRILL_DB" \
  --no-owner \
  --no-privileges \
  --exit-on-error

$COMPOSE exec -T citus_coordinator psql -U "$POSTGRES_USER" -d "$DRILL_DB" -v ON_ERROR_STOP=1 <<'SQL'
SELECT citus_version();
SELECT count(*) AS active_workers FROM citus_get_active_worker_nodes();
SELECT count(*) AS distributed_shards FROM pg_dist_shard;
SQL

echo "Restore drill completed successfully for backup: ${BACKUP_DIR}"

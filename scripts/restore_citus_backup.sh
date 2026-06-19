#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <backup_dir|coordinator_dump_file>" >&2
  exit 2
fi

INPUT="$1"
if [ -d "$INPUT" ]; then
  DUMP_FILE="${INPUT}/coordinator.dump"
  ./scripts/verify_backup.sh "$INPUT"
else
  DUMP_FILE="$INPUT"
fi

if [ ! -f "$DUMP_FILE" ]; then
  echo "Dump file not found: $DUMP_FILE" >&2
  exit 1
fi

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.workers.yml"
POSTGRES_USER="${POSTGRES_USER:-$(grep -E '^POSTGRES_USER=' .env 2>/dev/null | tail -1 | cut -d= -f2 || echo gr5)}"
POSTGRES_DB="${POSTGRES_DB:-$(grep -E '^POSTGRES_DB=' .env 2>/dev/null | tail -1 | cut -d= -f2 || echo gr5)}"

cat >&2 <<WARN
WARNING: this restores into ${POSTGRES_DB} and may replace existing objects.
Production workflow:
  1. stop application writes;
  2. verify backup checksums;
  3. test restore with scripts/backup_restore_drill.sh first;
  4. run restore;
  5. run smoke/integrity checks before enabling traffic.
WARN

if [ "${RESTORE_CONFIRM:-}" != "I_UNDERSTAND_THIS_REPLACES_DATA" ]; then
  echo "Set RESTORE_CONFIRM=I_UNDERSTAND_THIS_REPLACES_DATA to continue." >&2
  exit 3
fi

cat "$DUMP_FILE" | $COMPOSE exec -T citus_coordinator \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges --exit-on-error

$COMPOSE exec -T citus_coordinator psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 <<'SQL'
SELECT citus_version();
SELECT count(*) AS active_workers FROM citus_get_active_worker_nodes();
SELECT count(*) AS distributed_shards FROM pg_dist_shard;
SQL

echo "Restored Citus backup from ${DUMP_FILE}"

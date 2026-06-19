#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env

BACKUP_ROOT="${BACKUP_ROOT:-shared/backups}"
BACKUP_ID="${BACKUP_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
BACKUP_DIR="${BACKUP_DIR:-${BACKUP_ROOT}/${BACKUP_ID}}"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.workers.yml"
POSTGRES_USER="${POSTGRES_USER:-$(grep -E '^POSTGRES_USER=' .env 2>/dev/null | tail -1 | cut -d= -f2 || echo gr5)}"
POSTGRES_DB="${POSTGRES_DB:-$(grep -E '^POSTGRES_DB=' .env 2>/dev/null | tail -1 | cut -d= -f2 || echo gr5)}"

mkdir -p "$BACKUP_DIR"

cat > "${BACKUP_DIR}/manifest.json" <<JSON
{
  "backup_id": "${BACKUP_ID}",
  "created_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "type": "logical-citus-coordinator",
  "database": "${POSTGRES_DB}",
  "citus_worker_count": "${CITUS_WORKER_COUNT:-2}",
  "format": "pg_dump custom format",
  "restore_script": "scripts/restore_citus_backup.sh",
  "drill_script": "scripts/backup_restore_drill.sh"
}
JSON

echo "Backing up Citus coordinator/distributed schema through coordinator -> ${BACKUP_DIR}/coordinator.dump"
$COMPOSE exec -T citus_coordinator pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  -Fc \
  --serializable-deferrable \
  --no-owner \
  --no-privileges \
  > "${BACKUP_DIR}/coordinator.dump"

$COMPOSE exec -T citus_coordinator psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -XAtc \
  "select now(), citus_version(), count(*) from citus_get_active_worker_nodes();" \
  > "${BACKUP_DIR}/cluster_state.txt"

sha256sum "${BACKUP_DIR}/coordinator.dump" "${BACKUP_DIR}/manifest.json" "${BACKUP_DIR}/cluster_state.txt" \
  > "${BACKUP_DIR}/SHA256SUMS"

echo "Backup completed: ${BACKUP_DIR}"
echo "Next: run ./scripts/verify_backup.sh ${BACKUP_DIR} and ./scripts/backup_restore_drill.sh ${BACKUP_DIR}"

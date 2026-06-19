#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env

BACKUP_DIR="${1:-}"
if [ -n "$BACKUP_DIR" ]; then
  [ -f "${BACKUP_DIR}/SHA256SUMS" ] || { echo "SHA256SUMS not found in ${BACKUP_DIR}" >&2; exit 1; }
  [ -f "${BACKUP_DIR}/coordinator.dump" ] || { echo "coordinator.dump not found in ${BACKUP_DIR}" >&2; exit 1; }
  (cd "$BACKUP_DIR" && sha256sum -c SHA256SUMS)
  pg_restore --list "${BACKUP_DIR}/coordinator.dump" >/dev/null
  echo "Logical backup is readable and checksums are valid: ${BACKUP_DIR}"
  exit 0
fi

command -v pgbackrest >/dev/null || { echo "pgbackrest is required for physical backup verification" >&2; exit 1; }

STANZAS=(citus-coordinator)
for i in $(seq 1 "${CITUS_WORKER_COUNT:-2}"); do
  STANZAS+=("citus-worker${i}")
done

for stanza in "${STANZAS[@]}"; do
  echo "Checking ${stanza}"
  pgbackrest --stanza="${stanza}" check
  pgbackrest --stanza="${stanza}" info
  pgbackrest --stanza="${stanza}" expire --dry-run
done

#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env

TARGET_TIME="${1:?Usage: $0 '<YYYY-MM-DD HH:MM:SS+TZ>'}"
command -v pgbackrest >/dev/null || { echo "pgbackrest is required for PITR restore" >&2; exit 1; }

STANZAS=(citus-coordinator)
for i in $(seq 1 "${CITUS_WORKER_COUNT:-2}"); do
  STANZAS+=("citus-worker${i}")
done

cat >&2 <<'WARN'
WARNING: Citus PITR must restore coordinator and all workers to a consistent target time.
Stop application traffic before restore and validate cluster metadata after restore.
WARN

for stanza in "${STANZAS[@]}"; do
  echo "Restoring ${stanza} to ${TARGET_TIME}"
  pgbackrest --stanza="${stanza}" --type=time "--target=${TARGET_TIME}" restore
done

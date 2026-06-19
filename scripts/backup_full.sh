#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env

command -v pgbackrest >/dev/null || { echo "pgbackrest is required for production backup" >&2; exit 1; }

STANZAS=(citus-coordinator)
for i in $(seq 1 "${CITUS_WORKER_COUNT:-2}"); do
  STANZAS+=("citus-worker${i}")
done

for stanza in "${STANZAS[@]}"; do
  echo "Running full backup for ${stanza}"
  pgbackrest --stanza="${stanza}" backup --type=full
done

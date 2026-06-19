#!/usr/bin/env bash
set -euo pipefail

bad_files=$(find . \
  -path './.git' -prune -o \
  -path './shared' -prune -o \
  \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' -o -name '*.pyc' \) -print)
if [ -n "$bad_files" ]; then
  echo "Generated/cache files must not be committed:" >&2
  echo "$bad_files" >&2
  exit 1
fi

missing=0
for f in \
  scripts/init_tls_certs.sh \
  scripts/backup_all_shards.sh \
  scripts/verify_backup.sh \
  scripts/backup_restore_drill.sh \
  scripts/restore_citus_backup.sh; do
  if [ ! -x "$f" ]; then
    echo "Required executable script is missing or not executable: $f" >&2
    missing=1
  fi
done
[ "$missing" -eq 0 ]

grep -q 'DB_SSLMODE:.*verify-full' docker-compose.yml
grep -q 'PGBOUNCER_CLIENT_TLS_SSLMODE.*verify-ca' docker-compose.yml
grep -q 'cap_drop:' docker-compose.yml
grep -q 'read_only: true' docker-compose.yml

echo "Production hygiene checks passed."

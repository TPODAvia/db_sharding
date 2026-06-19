#!/usr/bin/env bash
set -euo pipefail

echo "This project now uses Citus, not manual shards." >&2
echo "Use: scripts/restore_citus_backup.sh <dump_file>" >&2
exit 2

#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env
# Backward-compatible wrapper. Production migrations go directly to Citus coordinator.
exec ./scripts/migrate_db_direct.sh "$@"

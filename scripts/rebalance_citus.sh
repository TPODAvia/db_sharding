#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env

MODE="${1:---dry-run}"
if [[ "$MODE" != "--dry-run" && "$MODE" != "--execute" ]]; then
  echo "Usage: $0 [--dry-run|--execute]" >&2
  exit 2
fi

COMPOSE_FILES=(-f docker-compose.yml)
if [[ -f docker-compose.workers.yml ]]; then
  COMPOSE_FILES+=(-f docker-compose.workers.yml)
fi

POSTGRES_USER="${POSTGRES_USER:-gr5}"
POSTGRES_DB="${POSTGRES_DB:-gr5}"

if [[ "$MODE" == "--dry-run" ]]; then
  docker compose "${COMPOSE_FILES[@]}" exec -T citus_coordinator \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 <<'SQL'
SELECT * FROM citus_get_active_worker_nodes();
SELECT shardid, shardstate, shardlength, nodename, nodeport
FROM pg_dist_shard_placement
ORDER BY nodename, shardid;
SQL
  echo "Dry-run only. Re-run with --execute during a maintenance window to move shards."
  exit 0
fi

cat >&2 <<'WARN'
WARNING: rebalance_table_shards can run for a long time and move significant data.
Run this during a maintenance window and watch Citus/Postgres metrics.
WARN

docker compose "${COMPOSE_FILES[@]}" exec -T citus_coordinator \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 <<'SQL'
SELECT rebalance_table_shards('orders');
SQL

#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <new_total_worker_count>" >&2
  echo "Example: $0 3" >&2
  exit 2
fi

NEW_COUNT="$1"
if ! [[ "$NEW_COUNT" =~ ^[0-9]+$ ]] || [ "$NEW_COUNT" -lt 1 ]; then
  echo "new_total_worker_count must be a positive integer" >&2
  exit 2
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Change secrets before production." >&2
fi

CURRENT_COUNT="$(grep -E '^CITUS_WORKER_COUNT=' .env | tail -1 | cut -d= -f2 || true)"
CURRENT_COUNT="${CURRENT_COUNT:-2}"
if [ "$NEW_COUNT" -lt "$CURRENT_COUNT" ]; then
  echo "Refusing to decrease CITUS_WORKER_COUNT: current=$CURRENT_COUNT new=$NEW_COUNT" >&2
  exit 1
fi

if grep -qE '^CITUS_WORKER_COUNT=' .env; then
  sed -i.bak "s/^CITUS_WORKER_COUNT=.*/CITUS_WORKER_COUNT=${NEW_COUNT}/" .env
else
  printf '\nCITUS_WORKER_COUNT=%s\n' "$NEW_COUNT" >> .env
fi

python3 scripts/render_citus_workers_compose.py "$NEW_COUNT"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.workers.yml"

$COMPOSE up -d citus_coordinator $(seq -f 'citus_worker%.0f' 1 "$NEW_COUNT") pgbouncer

./scripts/init_db_roles.sh

POSTGRES_USER="${POSTGRES_USER:-$(grep -E '^POSTGRES_USER=' .env | tail -1 | cut -d= -f2 || echo gr5)}"
POSTGRES_DB="${POSTGRES_DB:-$(grep -E '^POSTGRES_DB=' .env | tail -1 | cut -d= -f2 || echo gr5)}"

for worker in $(seq 1 "$NEW_COUNT"); do
  echo "Ensuring Citus extension on citus_worker${worker}"
  $COMPOSE exec -T "citus_worker${worker}" \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 \
    -c "CREATE EXTENSION IF NOT EXISTS citus;"

done

for worker in $(seq 1 "$NEW_COUNT"); do
  echo "Registering citus_worker${worker} in coordinator metadata"
  $COMPOSE exec -T citus_coordinator \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 <<SQL
CREATE EXTENSION IF NOT EXISTS citus;
DO \$\$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_dist_node
    WHERE nodename = 'citus_worker${worker}' AND nodeport = 5432
  ) THEN
    IF to_regproc('citus_add_node') IS NOT NULL THEN
      PERFORM citus_add_node('citus_worker${worker}', 5432);
    ELSE
      PERFORM master_add_node('citus_worker${worker}', 5432);
    END IF;
  END IF;
END
\$\$;
SQL
done

./scripts/migrate_db_direct.sh

# Rebalancing is what makes an added worker actually receive existing Citus
# shards. It can take time on large tables, but this script is intentionally a
# one-command production runbook. Set REBALANCE_AFTER_ADD=true to execute rebalancing immediately, or run scripts/rebalance_citus.sh later.
if [ "${REBALANCE_AFTER_ADD:-false}" = "true" ]; then
  echo "Rebalancing existing order shards across active workers"
  $COMPOSE exec -T citus_coordinator \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
  IF to_regproc('rebalance_table_shards') IS NOT NULL
     AND to_regclass('orders') IS NOT NULL
     AND EXISTS (SELECT 1 FROM pg_dist_partition WHERE logicalrelid = 'orders'::regclass) THEN
    PERFORM rebalance_table_shards('orders');
  END IF;
END
$$;
SQL
fi

$COMPOSE up -d --build writer_service reader_service

echo "DONE: CITUS_WORKER_COUNT=${NEW_COUNT}. Worker registered. Run REBALANCE_AFTER_ADD=true $0 ${NEW_COUNT} or ./scripts/rebalance_citus.sh --execute during a maintenance window to move existing shards."

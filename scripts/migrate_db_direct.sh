#!/usr/bin/env bash
set -euo pipefail

source ./scripts/lib_env.sh
load_dotenv .env

COMPOSE_FILES=(-f docker-compose.yml)
if [[ -f docker-compose.workers.yml ]]; then
  COMPOSE_FILES+=(-f docker-compose.workers.yml)
fi

# Run Alembic from app image but connect directly to coordinator:5432.
docker compose "${COMPOSE_FILES[@]}" run --rm \
  -e PGUSER="${MIGRATION_DB_USER:-migration_user}" \
  -e PGPASSWORD="${MIGRATION_DB_PASSWORD:-}" \
  -e PGPASSWORD_FILE="${MIGRATION_DB_PASSWORD_FILE:-/run/secrets/migration_db_password}" \
  -e PGBOUNCER_HOST=citus_coordinator \
  -e PGBOUNCER_PORT=5432 \
  -e MIGRATION_DB_HOST=citus_coordinator \
  -e MIGRATION_DB_PORT=5432 \
  writer_service alembic upgrade head

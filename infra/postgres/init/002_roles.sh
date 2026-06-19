#!/usr/bin/env bash
set -euo pipefail

read_secret() {
  local name="$1"
  local file_var="${name}_FILE"
  local file_value="${!file_var:-}"
  local value="${!name:-}"
  if [[ -n "$value" ]]; then
    printf '%s' "$value"
  elif [[ -n "$file_value" && -f "$file_value" ]]; then
    cat "$file_value"
  fi
}

APP_DB_USER="${APP_DB_USER:-app_user}"
MIGRATION_DB_USER="${MIGRATION_DB_USER:-migration_user}"
READONLY_DB_USER="${READONLY_DB_USER:-readonly_user}"
MONITORING_DB_USER="${MONITORING_DB_USER:-monitoring_user}"
BACKUP_DB_USER="${BACKUP_DB_USER:-backup_user}"

APP_DB_PASSWORD="$(read_secret APP_DB_PASSWORD)"
MIGRATION_DB_PASSWORD="$(read_secret MIGRATION_DB_PASSWORD)"
READONLY_DB_PASSWORD="$(read_secret READONLY_DB_PASSWORD)"
MONITORING_DB_PASSWORD="$(read_secret MONITORING_DB_PASSWORD)"
BACKUP_DB_PASSWORD="$(read_secret BACKUP_DB_PASSWORD)"

for item in APP_DB_PASSWORD MIGRATION_DB_PASSWORD READONLY_DB_PASSWORD MONITORING_DB_PASSWORD BACKUP_DB_PASSWORD; do
  if [[ -z "${!item:-}" ]]; then
    echo "$item or ${item}_FILE is required for DB role bootstrap" >&2
    exit 1
  fi
done

create_login_role() {
  local role="$1"
  local password="$2"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v role_name="$role" -v role_password="$password" <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role_name') THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', :'role_name', :'role_password');
  ELSE
    EXECUTE format('ALTER ROLE %I LOGIN PASSWORD %L', :'role_name', :'role_password');
  END IF;
END
$$;
SQL
}

create_login_role "$APP_DB_USER" "$APP_DB_PASSWORD"
create_login_role "$MIGRATION_DB_USER" "$MIGRATION_DB_PASSWORD"
create_login_role "$READONLY_DB_USER" "$READONLY_DB_PASSWORD"
create_login_role "$MONITORING_DB_USER" "$MONITORING_DB_PASSWORD"
create_login_role "$BACKUP_DB_USER" "$BACKUP_DB_PASSWORD"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_user="$APP_DB_USER" \
  -v migration_user="$MIGRATION_DB_USER" \
  -v readonly_user="$READONLY_DB_USER" \
  -v monitoring_user="$MONITORING_DB_USER" \
  -v backup_user="$BACKUP_DB_USER" -v dbname="$POSTGRES_DB" <<'SQL'
GRANT CONNECT ON DATABASE :"dbname" TO :"app_user", :"migration_user", :"readonly_user", :"monitoring_user", :"backup_user";
GRANT CREATE, USAGE ON SCHEMA public TO :"migration_user";
GRANT USAGE ON SCHEMA public TO :"app_user", :"readonly_user", :"monitoring_user";
GRANT pg_monitor TO :"monitoring_user";
ALTER ROLE :"backup_user" WITH REPLICATION;
SQL

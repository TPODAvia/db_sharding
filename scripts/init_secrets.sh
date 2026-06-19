#!/usr/bin/env bash
set -euo pipefail

mkdir -p docker/secrets
umask 077
make_secret() {
  local target="$1"
  if [[ ! -f "$target" ]]; then
    python3 - <<'PY' > "$target"
import secrets
print(secrets.token_urlsafe(48))
PY
    echo "created $target"
  else
    echo "exists  $target"
  fi
}
make_secret docker/secrets/postgres_password.txt
make_secret docker/secrets/app_api_key_read.txt
make_secret docker/secrets/app_api_key_write.txt
make_secret docker/secrets/app_api_key_admin.txt
make_secret docker/secrets/jwt_secret.txt
make_secret docker/secrets/app_db_password.txt
make_secret docker/secrets/migration_db_password.txt
make_secret docker/secrets/readonly_db_password.txt
make_secret docker/secrets/monitoring_db_password.txt
make_secret docker/secrets/backup_db_password.txt
make_secret docker/secrets/metrics_token.txt

#!/usr/bin/env bash
# Shared helpers for local runbooks. Docker Compose reads .env automatically, but shell scripts do not.
load_dotenv() {
  local file="${1:-.env}"
  if [[ -f "$file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$file"
    set +a
  fi
}

compose_files_args() {
  printf -- '-f docker-compose.yml '
  if [[ -f docker-compose.workers.yml ]]; then
    printf -- '-f docker-compose.workers.yml '
  fi
}

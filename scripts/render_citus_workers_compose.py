#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

BASE_WORKERS = 2


def render(worker_count: int) -> str:
    if worker_count <= BASE_WORKERS:
        return "services: {}\n"

    lines = ["services:"]

    for worker in range(BASE_WORKERS + 1, worker_count + 1):
        host_port = 5432 + worker
        lines.extend(
            [
                f"  citus_worker{worker}:",
                "    build:",
                "      context: .",
                "      dockerfile: infra/citus.Dockerfile",
                "      args:",
                "        CITUS_IMAGE: ${CITUS_IMAGE:-citusdata/citus:14-pg16}",
                "    restart: unless-stopped",
                "    command:",
                "      - postgres",
                "      - -c",
                "      - shared_preload_libraries=citus",
                "      - -c",
                "      - password_encryption=scram-sha-256",
                "      - -c",
                "      - statement_timeout=30s",
                "      - -c",
                "      - idle_in_transaction_session_timeout=60s",
                "      - -c",
                "      - ssl=on",
                "      - -c",
                "      - ssl_cert_file=/var/lib/postgresql/tls/server.crt",
                "      - -c",
                "      - ssl_key_file=/var/lib/postgresql/tls/server.key",
                "      - -c",
                "      - ssl_ca_file=/var/lib/postgresql/tls/ca.crt",
                "    environment:",
                "      POSTGRES_DB: ${POSTGRES_DB:?POSTGRES_DB is required}",
                "      POSTGRES_USER: ${POSTGRES_USER:?POSTGRES_USER is required}",
                "      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-}",
                "      POSTGRES_PASSWORD_FILE: ${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}",
                "      APP_DB_USER: ${APP_DB_USER:-app_user}",
                "      APP_DB_PASSWORD: ${APP_DB_PASSWORD:-}",
                "      APP_DB_PASSWORD_FILE: ${APP_DB_PASSWORD_FILE:-/run/secrets/app_db_password}",
                "      MIGRATION_DB_USER: ${MIGRATION_DB_USER:-migration_user}",
                "      MIGRATION_DB_PASSWORD: ${MIGRATION_DB_PASSWORD:-}",
                "      MIGRATION_DB_PASSWORD_FILE: ${MIGRATION_DB_PASSWORD_FILE:-/run/secrets/migration_db_password}",
                "      READONLY_DB_USER: ${READONLY_DB_USER:-readonly_user}",
                "      READONLY_DB_PASSWORD: ${READONLY_DB_PASSWORD:-}",
                "      READONLY_DB_PASSWORD_FILE: ${READONLY_DB_PASSWORD_FILE:-/run/secrets/readonly_db_password}",
                "      MONITORING_DB_USER: ${MONITORING_DB_USER:-monitoring_user}",
                "      MONITORING_DB_PASSWORD: ${MONITORING_DB_PASSWORD:-}",
                (
                    "      MONITORING_DB_PASSWORD_FILE: "
                    "${MONITORING_DB_PASSWORD_FILE:-/run/secrets/monitoring_db_password}"
                ),
                "      BACKUP_DB_USER: ${BACKUP_DB_USER:-backup_user}",
                "      BACKUP_DB_PASSWORD: ${BACKUP_DB_PASSWORD:-}",
                "      BACKUP_DB_PASSWORD_FILE: ${BACKUP_DB_PASSWORD_FILE:-/run/secrets/backup_db_password}",
                "      TZ: ${TZ:-Europe/Zagreb}",
                "      POSTGRES_SSL: ${POSTGRES_SSL:-on}",
                "    ports:",
                f"      - \"127.0.0.1:{host_port}:5432\"",
                "    volumes:",
                f"      - ./shared/data/citus_worker{worker}:/var/lib/postgresql/data",
                "      - ./infra/postgres/init:/docker-entrypoint-initdb.d:ro",
                "      - ./infra/tls/certs:/certs:ro",
                "    healthcheck:",
                "      test: [\"CMD-SHELL\", \"pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}\"]",
                "      interval: 5s",
                "      timeout: 5s",
                "      retries: 30",
                "    security_opt:",
                "      - no-new-privileges:true",
                "    cap_drop:",
                "      - ALL",
                "    cap_add:",
                "      - CHOWN",
                "      - FOWNER",
                "      - DAC_OVERRIDE",
                "      - SETUID",
                "      - SETGID",
                "    pids_limit: 512",
                "    mem_limit: ${POSTGRES_MEM_LIMIT:-1g}",
                "    cpus: ${POSTGRES_CPUS:-1.0}",
                "    secrets:",
                "      - postgres_password",
                "      - app_db_password",
                "      - migration_db_password",
                "      - readonly_db_password",
                "      - monitoring_db_password",
                "      - backup_db_password",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("worker_count", type=int)
    parser.add_argument("--output", default="docker-compose.workers.yml")
    args = parser.parse_args()
    if args.worker_count < 1:
        raise SystemExit("worker_count must be >= 1")
    Path(args.output).write_text(render(args.worker_count), encoding="utf-8")
    print(f"Generated {args.output} for CITUS_WORKER_COUNT={args.worker_count}")


if __name__ == "__main__":
    main()

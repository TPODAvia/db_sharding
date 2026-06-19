from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import URL, create_engine, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.common.env import get_env_or_file  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def database_url() -> URL:
    user = os.environ["PGUSER"]
    password = get_env_or_file("PGPASSWORD") or ""
    # Citus DDL/migrations should use a direct coordinator connection, not PgBouncer transaction pooling.
    host = os.getenv("MIGRATION_DB_HOST", os.getenv("PGBOUNCER_HOST", "citus_coordinator"))
    port = int(os.getenv("MIGRATION_DB_PORT", "5432"))
    db = os.environ["PGDATABASE"]
    return URL.create(
        "postgresql+psycopg",
        username=user,
        password=password,
        host=host,
        port=port,
        database=db,
    )


def run_migrations_online() -> None:
    connectable = create_engine(database_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()

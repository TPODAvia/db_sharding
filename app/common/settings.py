from __future__ import annotations

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    pg_user: str = os.getenv("PGUSER", "gr5")
    pg_password: str = os.getenv("PGPASSWORD", "admin")
    pgbouncer_host: str = os.getenv("PGBOUNCER_HOST", "localhost")
    pgbouncer_port: int = int(os.getenv("PGBOUNCER_PORT", "6432"))
    shard_count: int = int(os.getenv("SHARD_COUNT", "2"))
    snowflake_worker_id: int = int(os.getenv("SNOWFLAKE_WORKER_ID", "1"))


settings = Settings()
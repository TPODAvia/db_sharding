from __future__ import annotations

import asyncio
import logging
import ssl
from dataclasses import dataclass

import asyncpg

from app.common.security import inc_metric
from app.common.settings import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Database:
    pool: asyncpg.Pool


class DatabasePool:
    """Single connection pool to the Citus coordinator.

    Citus owns physical shard placement. The application must not calculate
    shard numbers or connect to worker nodes directly.
    """

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        await conn.execute("SELECT set_config('statement_timeout', $1, false)", str(settings.db_statement_timeout_ms))
        await conn.execute(
            "SELECT set_config('idle_in_transaction_session_timeout', $1, false)",
            str(settings.db_idle_transaction_timeout_ms),
        )

    def _ssl_context(self) -> ssl.SSLContext | None:
        mode = settings.db_sslmode
        if mode in {"disable", "prefer"}:
            return None
        if mode == "require":
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        else:
            ctx = ssl.create_default_context(cafile=settings.db_ssl_ca_file)
            ctx.check_hostname = mode == "verify-full"
            ctx.verify_mode = ssl.CERT_REQUIRED
        if settings.db_ssl_cert_file and settings.db_ssl_key_file:
            ctx.load_cert_chain(settings.db_ssl_cert_file, settings.db_ssl_key_file)
        return ctx

    async def start(self) -> None:
        last_error: Exception | None = None
        for attempt in range(1, settings.db_connect_retries + 1):
            try:
                self._pool = await asyncpg.create_pool(
                    user=settings.pg_user,
                    password=settings.pg_password,
                    database=settings.pg_database,
                    host=settings.pgbouncer_host,
                    port=settings.pgbouncer_port,
                    min_size=settings.db_pool_min_size,
                    max_size=settings.db_pool_max_size,
                    command_timeout=settings.db_command_timeout_seconds,
                    max_inactive_connection_lifetime=60,
                    statement_cache_size=0,
                    ssl=self._ssl_context(),
                    init=self._init_connection,
                )
                logger.info("Connected to Citus coordinator through PgBouncer database=%s", settings.pg_database)
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning("DB connect failed, attempt=%s: %s", attempt, exc)
                await asyncio.sleep(settings.db_connect_retry_delay_seconds)
        raise RuntimeError("Could not connect to Citus coordinator through PgBouncer") from last_error

    async def stop(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool is not started")
        return self._pool

    async def readiness(self) -> dict[str, str]:
        try:
            await self.pool.fetchval("SELECT 1")
            citus_version = await self.pool.fetchval("SELECT citus_version()")
            workers = await self.pool.fetchval("SELECT count(*) FROM citus_get_active_worker_nodes()")
            inc_metric("citus_active_workers", float(workers or 0))
            shard_count = await self.pool.fetchval("SELECT count(*) FROM pg_dist_shard")
            inc_metric("citus_shard_count", float(shard_count or 0))
            return {
                "coordinator": "ok",
                "citus": "ok",
                "citus_version": str(citus_version),
                "active_workers": str(workers),
                "distributed_shards": str(shard_count),
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("Readiness failed")
            return {"coordinator": f"error: {type(exc).__name__}"}

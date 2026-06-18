from __future__ import annotations
import asyncio
from dataclasses import dataclass

import asyncpg

from app.common.settings import settings
from app.common.sharding import shard_database_name, shard_number_for_user

@dataclass
class ShardPool:
    shard_number: int
    pool: asyncpg.Pool

class ShardRouter:
    def __init__(self) -> None:
        self._pools: dict[int, asyncpg.Pool] = {}

    async def start(self) -> None:
        for shard_number in range(1, settings.shard_count + 1):
            db_name = shard_database_name(shard_number)
            last_error: Exception | None = None
            for _ in range(30):
                try:
                    self._pools[shard_number] = await asyncpg.create_pool(
                        user=settings.pg_user,
                        password=settings.pg_password,
                        database=db_name,
                        host=settings.pgbouncer_host,
                        port=settings.pgbouncer_port,
                        min_size=1,
                        max_size=10,
                        statement_cache_size=0,  # recommended with PgBouncer transaction pooling
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    await asyncio.sleep(1)
            else:
                raise RuntimeError(f"Could not connect to {db_name} through PgBouncer") from last_error
    
    async def stop(self) -> None:
        for pool in self._pools.values():
            await pool.close()
    
    def pool_by_user_id(self, user_id: int) -> ShardPool:
        shard_number = shard_number_for_user(user_id, settings.shard_count)
        return ShardPool(shard_number=shard_number, pool=self._pools[shard_number])
    
    def all_shards(self) -> list[ShardPool]:
        return [ShardPool(shard_number=n, pool=p) for n,p in sorted(self._pools.items())]
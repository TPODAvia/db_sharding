from __future__ import annotations

from decimal import Decimal
from typing import Any
from app.common.db import ShardRouter
from app.common.snowflake import SnowflakeGenerator
import json

class OrderRepository:
    def __init__(self, router: ShardRouter, snowflake: SnowflakeGenerator | None = None):
        self.router = router
        self.snowflake = snowflake

    async def create_order(
        self,
        *,
        user_id: int,
        amount: Decimal,
        status: str = "pending",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.snowflake is None:
            raise RuntimeError("snowflake generator is required for create_order")
        
        order_id = self.snowflake.next_id()
        shard = self.router.pool_by_user_id(user_id)
        row = await shard.pool.fetchrow(
            """
            INSERT INTO orders(id, user_id, amount, status, payload)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id, user_id, amount, status, payload, created_at, updated_at
            """,
            order_id,
            user_id,
            amount,
            status,
            json.dumps(payload) or {},
        )
        result = dict(row)
        result["shard"] = shard.shard_number
        return result

    async def get_order_by_id(self, order_id: int) -> dict[str, Any] | None:
        for shard in self.router.all_shards():
            row = await shard.pool.fetchrow(
                """
                SELECT id, user_id, amount, status, payload, created_at, updated_at
                FROM orders
                WHERE id = $1
                """,
                order_id,
            )
            if row:
                result = dict(row)
                result["shard"] = shard.shard_number
                return result
        return None

    async def list_orders_by_user(self, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
        shard = self.router.pool_by_user_id(user_id)
        rows = await shard.pool.fetch(
            """
            SELECT id, user_id, amount, status, payload, created_at, updated_at
            FROM orders
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
        return [dict(row) | {"shard": shard.shard_number} for row in rows]

    async def list_pending_orders(self, limit_per_shard: int = 20) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for shard in self.router.all_shards():
            rows = await shard.pool.fetch(
                """
                SELECT id, user_id, amount, status, payload, created_at, updated_at
                FROM orders
                WHERE status = 'pending'
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit_per_shard,
            )
            result.extend(dict(row) | {"shard": shard.shard_number} for row in rows)
        result.sort(key=lambda item: item["created_at"], reverse=True)
        return result

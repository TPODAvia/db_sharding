from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from app.common.db import DatabasePool
from app.common.security import inc_metric
from app.common.settings import settings
from app.common.uuidv7 import new_uuidv7


class IdempotencyKeyConflictError(RuntimeError):
    """Raised when an idempotency key is reused with a different request body."""


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def to_jsonb(value: Any) -> str:
    """Serialize Python values to a stable JSON string accepted by asyncpg for jsonb."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)


def idempotency_request_hash(*, user_id: int, amount: Decimal, status: str, payload: dict[str, Any] | None) -> str:
    canonical = {
        "user_id": user_id,
        "amount": format(amount, "f"),
        "status": status,
        "payload": payload or {},
    }
    return hashlib.sha256(to_jsonb(canonical).encode("utf-8")).hexdigest()


class OrderRepository:
    def __init__(self, db: DatabasePool):
        self.db = db

    async def create_order(
        self,
        *,
        user_id: int,
        amount: Decimal,
        status: str = "pending",
        payload: dict[str, Any] | None = None,
        principal: str = "anonymous",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        order_id = new_uuidv7()
        request_hash = idempotency_request_hash(user_id=user_id, amount=amount, status=status, payload=payload)
        payload_json = to_jsonb(payload or {})
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                if idempotency_key:
                    existing = await conn.fetchrow(
                        """
                        SELECT request_hash, response
                        FROM idempotency_keys
                        WHERE principal = $1 AND idempotency_key = $2
                        """,
                        principal,
                        idempotency_key,
                    )
                    if existing:
                        if existing["request_hash"] != request_hash:
                            inc_metric("idempotency_conflicts_total")
                            raise IdempotencyKeyConflictError(
                                "Idempotency-Key was reused with a different request body"
                            )
                        if existing["response"] is not None:
                            inc_metric("idempotency_replays_total")
                            return dict(existing["response"])
                    else:
                        try:
                            await conn.execute(
                                """
                                INSERT INTO idempotency_keys(principal, idempotency_key, request_hash)
                                VALUES ($1, $2, $3)
                                """,
                                principal,
                                idempotency_key,
                                request_hash,
                            )
                        except asyncpg.UniqueViolationError:
                            existing = await conn.fetchrow(
                                """
                                SELECT request_hash, response
                                FROM idempotency_keys
                                WHERE principal = $1 AND idempotency_key = $2
                                """,
                                principal,
                                idempotency_key,
                            )
                            if existing:
                                if existing["request_hash"] != request_hash:
                                    inc_metric("idempotency_conflicts_total")
                                    raise IdempotencyKeyConflictError(
                                        "Idempotency-Key was reused with a different request body"
                                    ) from None
                                if existing["response"] is not None:
                                    inc_metric("idempotency_replays_total")
                                    return dict(existing["response"])
                            raise

                row = await conn.fetchrow(
                    """
                    INSERT INTO orders(id, user_id, amount, status, payload)
                    VALUES ($1, $2, $3, $4, $5::jsonb)
                    RETURNING id, user_id, amount, status, payload, created_at, updated_at
                    """,
                    order_id,
                    user_id,
                    amount,
                    status,
                    payload_json,
                )
                result = dict(row)
                if idempotency_key:
                    await conn.execute(
                        """
                        UPDATE idempotency_keys
                        SET response = $3::jsonb, updated_at = now()
                        WHERE principal = $1 AND idempotency_key = $2
                        """,
                        principal,
                        idempotency_key,
                        to_jsonb(result),
                    )
        return result

    async def get_order_by_id_admin(self, order_id: UUID) -> dict[str, Any] | None:
        # Admin-only fan-out lookup. Normal public API must include user_id to
        # let Citus route by the distribution column.
        row = await self.db.pool.fetchrow(
            """
            SELECT id, user_id, amount, status, payload, created_at, updated_at
            FROM orders
            WHERE id = $1
            LIMIT 1
            """,
            order_id,
        )
        return dict(row) if row else None

    async def get_order_by_user_and_id(self, *, user_id: int, order_id: UUID) -> dict[str, Any] | None:
        row = await self.db.pool.fetchrow(
            """
            SELECT id, user_id, amount, status, payload, created_at, updated_at
            FROM orders
            WHERE user_id = $1 AND id = $2
            """,
            user_id,
            order_id,
        )
        return dict(row) if row else None

    async def list_orders_by_user(self, user_id: int, limit: int | None = None) -> list[dict[str, Any]]:
        safe_limit = min(limit or settings.default_list_limit, settings.max_list_limit)
        rows = await self.db.pool.fetch(
            """
            SELECT id, user_id, amount, status, payload, created_at, updated_at
            FROM orders
            WHERE user_id = $1
            ORDER BY created_at DESC, id DESC
            LIMIT $2
            """,
            user_id,
            safe_limit,
        )
        return [dict(row) for row in rows]

    async def list_pending_orders_admin(self, limit: int | None = None) -> list[dict[str, Any]]:
        safe_limit = min(limit or 20, settings.max_list_limit)
        rows = await self.db.pool.fetch(
            """
            SELECT id, user_id, amount, status, payload, created_at, updated_at
            FROM orders
            WHERE status = 'pending'
            ORDER BY created_at DESC, id DESC
            LIMIT $1
            """,
            safe_limit,
        )
        return [dict(row) for row in rows]

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from app.common.db import ShardRouter
from app.common.repository import OrderRepository

app = FastAPI(title="Reader service")
router = ShardRouter()
repo = OrderRepository(router=router)


@app.on_event("startup")
async def startup() -> None:
    await router.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await router.stop()


@app.get("/users/{user_id}/orders")
async def list_user_orders(user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    return await repo.list_orders_by_user(user_id=user_id, limit=limit)


@app.get("/orders/pending")
async def list_pending(limit_per_shard: int = 20) -> list[dict[str, Any]]:
    # This query uses partial index idx_orders_pending_created on each shard.
    return await repo.list_pending_orders(limit_per_shard=limit_per_shard)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

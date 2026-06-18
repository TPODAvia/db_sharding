from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.common.db import ShardRouter
from app.common.repository import OrderRepository
from app.common.settings import settings
from app.common.snowflake import SnowflakeGenerator


class CreateOrderRequest(BaseModel):
    user_id: int = Field(gt=0)
    amount: Decimal = Field(ge=0)
    status: str = "pending"
    payload: dict[str, Any] = Field(default_factory=dict)


app = FastAPI(title="Writer service")
router = ShardRouter()
snowflake = SnowflakeGenerator(worker_id=settings.snowflake_worker_id)
repo = OrderRepository(router=router, snowflake=snowflake)


@app.on_event("startup")
async def startup() -> None:
    await router.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await router.stop()


@app.post("/orders")
async def create_order(request: CreateOrderRequest) -> dict[str, Any]:
    if request.status not in {"pending", "paid", "cancelled"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    return await repo.create_order(
        user_id=request.user_id,
        amount=request.amount,
        status=request.status,
        payload=request.payload,
    )


@app.get("/orders/{order_id}")
async def get_order(order_id: int) -> dict[str, Any]:
    order = await repo.get_order_by_id(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.get("/snowflake/{order_id}/parse")
def parse_snowflake(order_id: int) -> dict[str, int]:
    return snowflake.parse(order_id)

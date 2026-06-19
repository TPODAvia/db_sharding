from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request
from pydantic import BaseModel, Field, field_validator

from app.common.api import create_app
from app.common.db import DatabasePool
from app.common.repository import IdempotencyKeyConflictError, OrderRepository
from app.common.security import payload_size_bytes, require_role, require_tenant_access
from app.common.settings import settings


class OrderStatus(StrEnum):
    pending = "pending"
    paid = "paid"
    cancelled = "cancelled"


class CreateOrderRequest(BaseModel):
    user_id: int = Field(gt=0)
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    status: OrderStatus = OrderStatus.pending
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("amount")
    @classmethod
    def amount_is_reasonable(cls, value: Decimal) -> Decimal:
        if value > settings.max_order_amount:
            raise ValueError(f"amount must be <= {settings.max_order_amount}")
        return value

    @field_validator("payload")
    @classmethod
    def payload_is_small(cls, value: dict[str, Any]) -> dict[str, Any]:
        if payload_size_bytes(value) > settings.max_payload_bytes:
            raise ValueError(f"payload is too large; max {settings.max_payload_bytes} bytes")
        return value


db = DatabasePool()
repo = OrderRepository(db=db)
app = create_app(title="Writer service", db=db)
router = APIRouter(prefix="/api/v1")


@router.post("/orders", dependencies=[Depends(require_role("orders:write"))])
async def create_order(
    body: CreateOrderRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=16, max_length=256),
) -> dict[str, Any]:
    require_tenant_access(request, body.user_id)
    principal = getattr(request.state, "principal", None)
    principal_id = getattr(principal, "subject", "anonymous")
    try:
        return await repo.create_order(
            user_id=body.user_id,
            amount=body.amount,
            status=body.status.value,
            payload=body.payload,
            principal=principal_id,
            idempotency_key=idempotency_key,
        )
    except IdempotencyKeyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/users/{user_id}/orders/{order_id}", dependencies=[Depends(require_role("orders:read"))])
async def get_user_order(request: Request, user_id: int = Path(gt=0), order_id: UUID = Path()) -> dict[str, Any]:
    require_tenant_access(request, user_id)
    order = await repo.get_order_by_user_and_id(user_id=user_id, order_id=order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/admin/orders/{order_id}", dependencies=[Depends(require_role("admin"))])
async def get_order_admin(order_id: UUID) -> dict[str, Any]:
    order = await repo.get_order_by_id_admin(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return await db.readiness()


app.include_router(router)

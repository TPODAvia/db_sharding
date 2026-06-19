from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from app.common.api import create_app
from app.common.db import DatabasePool
from app.common.repository import OrderRepository
from app.common.security import require_role, require_tenant_access
from app.common.settings import settings

db = DatabasePool()
repo = OrderRepository(db=db)
app = create_app(title="Reader service", db=db)
router = APIRouter(prefix="/api/v1")


@router.get("/users/{user_id}/orders", dependencies=[Depends(require_role("orders:read"))])
async def list_user_orders(
    request: Request,
    user_id: int = Path(gt=0),
    limit: int = Query(default=settings.default_list_limit, ge=1, le=settings.max_list_limit),
) -> list[dict[str, Any]]:
    require_tenant_access(request, user_id)
    return await repo.list_orders_by_user(user_id=user_id, limit=limit)


@router.get("/users/{user_id}/orders/{order_id}", dependencies=[Depends(require_role("orders:read"))])
async def get_user_order(request: Request, user_id: int = Path(gt=0), order_id: UUID = Path()) -> dict[str, Any]:
    require_tenant_access(request, user_id)
    order = await repo.get_order_by_user_and_id(user_id=user_id, order_id=order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/admin/orders/pending", dependencies=[Depends(require_role("admin"))])
async def list_pending_admin(
    limit: int = Query(default=20, ge=1, le=settings.max_list_limit),
) -> list[dict[str, Any]]:
    return await repo.list_pending_orders_admin(limit=limit)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return await db.readiness()


app.include_router(router)

from __future__ import annotations

import asyncio
import os
import random
from decimal import Decimal

from app.common.db import ShardRouter
from app.common.repository import OrderRepository
from app.common.settings import settings
from app.common.snowflake import SnowflakeGenerator


async def main() -> None:
    interval = float(os.getenv("PRODUCER_INTERVAL_SECONDS", "2"))
    router = ShardRouter()
    await router.start()
    repo = OrderRepository(
        router=router,
        snowflake=SnowflakeGenerator(worker_id=settings.snowflake_worker_id),
    )
    try:
        while True:
            user_id = random.randint(1, 10)
            amount = Decimal(random.randint(100, 10000)) / Decimal("100")
            order = await repo.create_order(
                user_id=user_id,
                amount=amount,
                status=random.choice(["pending", "pending", "paid"]),
                payload={"source": "producer_service"},
            )
            print(f"created order_id={order['id']} user_id={user_id} shard={order['shard']}", flush=True)
            await asyncio.sleep(interval)
    finally:
        await router.stop()


if __name__ == "__main__":
    asyncio.run(main())

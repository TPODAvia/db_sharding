from __future__ import annotations

import asyncio
import logging
import os
import random
from decimal import Decimal

from app.common.db import DatabasePool
from app.common.repository import OrderRepository
from app.common.settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


async def main() -> None:
    interval = float(os.getenv("PRODUCER_INTERVAL_SECONDS", "2"))
    db = DatabasePool()
    await db.start()
    repo = OrderRepository(db=db)
    try:
        while True:
            # Demo data generator only; not used for secrets or security decisions.
            user_id = random.randint(1, 10)  # nosec B311
            amount = Decimal(random.randint(100, 10000)) / Decimal("100")  # nosec B311
            order = await repo.create_order(
                user_id=user_id,
                amount=amount,
                status=random.choice(["pending", "pending", "paid"]),  # nosec B311
                payload={"source": "producer_service"},
            )
            logger.info("created order_id=%s user_id=%s", order["id"], user_id)
            await asyncio.sleep(interval)
    finally:
        await db.stop()


if __name__ == "__main__":
    asyncio.run(main())

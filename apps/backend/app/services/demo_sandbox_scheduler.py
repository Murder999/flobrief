from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.demo_sandbox_service import terminate_expired_sandboxes

logger = logging.getLogger(__name__)


async def _run() -> None:
    while True:
        try:
            async with AsyncSessionLocal() as db:
                cleaned = await terminate_expired_sandboxes(db)
                if cleaned:
                    logger.info("Expired %s demo sandbox(es)", cleaned)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Demo sandbox cleanup failed")
        await asyncio.sleep(max(30, settings.DEMO_SANDBOX_CLEANUP_INTERVAL_SECONDS))


def start_demo_sandbox_scheduler() -> asyncio.Task[None]:
    return asyncio.create_task(_run(), name="demo-sandbox-cleanup")

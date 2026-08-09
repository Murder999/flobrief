from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityLog
from app.repositories.activity import ActivityLogRepository


class ActivityLogService:
    """Service for writing immutable tenant-scoped activity log entries.

    Call log() from API handlers via background_tasks.add_task() for fire-and-forget logging.
    Never call update() or delete() on ActivityLog rows.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._repo = ActivityLogRepository(db)

    async def log(
        self,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        agency_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        meta: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ActivityLog:
        return await self._repo.create(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            agency_id=agency_id,
            brand_id=brand_id,
            actor_user_id=actor_user_id,
            meta=meta,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def list_for_agency(
        self,
        agency_id: uuid.UUID,
        entity_type: str | None = None,
        actor_user_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ActivityLog], int]:
        items = await self._repo.list_for_agency(
            agency_id=agency_id,
            entity_type=entity_type,
            actor_user_id=actor_user_id,
            limit=limit,
            offset=offset,
        )
        total = await self._repo.count_for_agency(
            agency_id=agency_id,
            entity_type=entity_type,
            actor_user_id=actor_user_id,
        )
        return items, total

    async def list_for_entity(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        limit: int = 20,
    ) -> list[ActivityLog]:
        return await self._repo.list_for_entity(
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
        )

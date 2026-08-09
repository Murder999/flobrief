from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityLog


class ActivityLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
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
        log = ActivityLog(
            id=uuid.uuid4(),
            created_at=datetime.now(UTC),
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
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def list_for_agency(
        self,
        agency_id: uuid.UUID,
        entity_type: str | None = None,
        actor_user_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ActivityLog]:
        stmt = (
            select(ActivityLog)
            .where(ActivityLog.agency_id == agency_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if entity_type:
            stmt = stmt.where(ActivityLog.entity_type == entity_type)
        if actor_user_id:
            stmt = stmt.where(ActivityLog.actor_user_id == actor_user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_agency(
        self,
        agency_id: uuid.UUID,
        entity_type: str | None = None,
        actor_user_id: uuid.UUID | None = None,
    ) -> int:
        stmt = (
            select(func.count()).select_from(ActivityLog).where(ActivityLog.agency_id == agency_id)
        )
        if entity_type:
            stmt = stmt.where(ActivityLog.entity_type == entity_type)
        if actor_user_id:
            stmt = stmt.where(ActivityLog.actor_user_id == actor_user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def list_for_entity(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        limit: int = 20,
    ) -> list[ActivityLog]:
        stmt = (
            select(ActivityLog)
            .where(
                ActivityLog.entity_type == entity_type,
                ActivityLog.entity_id == entity_id,
            )
            .order_by(ActivityLog.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

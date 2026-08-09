from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_allocation import WorkAllocation


class WorkAllocationRepository:
    """Query surface for WorkAllocation rows. `WorkAllocationService` (Phase 2)
    consumes this — Phase 1 only ships the model + repository, no service/API."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(
        self, allocation_id: uuid.UUID, agency_id: uuid.UUID
    ) -> WorkAllocation | None:
        result = await self.db.execute(
            select(WorkAllocation).where(
                WorkAllocation.id == allocation_id,
                WorkAllocation.agency_id == agency_id,
                WorkAllocation.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        start: date | None = None,
        end: date | None = None,
    ) -> list[WorkAllocation]:
        conditions = [
            WorkAllocation.agency_id == agency_id,
            WorkAllocation.user_id == user_id,
            WorkAllocation.deleted_at.is_(None),
        ]
        if start is not None:
            conditions.append(WorkAllocation.end_date >= start)
        if end is not None:
            conditions.append(WorkAllocation.start_date <= end)
        result = await self.db.execute(
            select(WorkAllocation).where(*conditions).order_by(WorkAllocation.start_date.asc())
        )
        return list(result.scalars().all())

    async def list_for_brief(
        self, agency_id: uuid.UUID, brief_id: uuid.UUID
    ) -> list[WorkAllocation]:
        result = await self.db.execute(
            select(WorkAllocation)
            .where(
                WorkAllocation.agency_id == agency_id,
                WorkAllocation.brief_id == brief_id,
                WorkAllocation.deleted_at.is_(None),
            )
            .order_by(WorkAllocation.start_date.asc())
        )
        return list(result.scalars().all())

    async def create(self, data: dict) -> WorkAllocation:
        obj = WorkAllocation(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, obj: WorkAllocation, data: dict) -> WorkAllocation:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        return obj

    async def soft_delete(self, obj: WorkAllocation) -> None:
        obj.soft_delete()
        await self.db.flush()

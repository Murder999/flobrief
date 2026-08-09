from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency_settings import AgencySettings


class AgencySettingsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_agency(self, agency_id: uuid.UUID) -> AgencySettings | None:
        result = await self.db.execute(
            select(AgencySettings).where(
                AgencySettings.agency_id == agency_id,
                AgencySettings.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_agency_for_update(self, agency_id: uuid.UUID) -> AgencySettings | None:
        """`SELECT ... FOR UPDATE` — the row lock that makes concurrent
        `invoice_number_seq` increments safe (plan §3). Must be called
        inside the same transaction as the invoice insert; the lock is held
        until that transaction commits/rolls back, so a second concurrent
        caller blocks here until the first one finishes."""
        result = await self.db.execute(
            select(AgencySettings)
            .where(
                AgencySettings.agency_id == agency_id,
                AgencySettings.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> AgencySettings:
        obj = AgencySettings(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, obj: AgencySettings, data: dict) -> AgencySettings:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        return obj

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capacity_exception import CapacityException


class CapacityExceptionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(
        self, exception_id: uuid.UUID, agency_id: uuid.UUID
    ) -> CapacityException | None:
        result = await self.db.execute(
            select(CapacityException).where(
                CapacityException.id == exception_id,
                CapacityException.agency_id == agency_id,
                CapacityException.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_for_user_date(
        self, agency_id: uuid.UUID, user_id: uuid.UUID, exception_date: date
    ) -> CapacityException | None:
        result = await self.db.execute(
            select(CapacityException).where(
                CapacityException.agency_id == agency_id,
                CapacityException.user_id == user_id,
                CapacityException.date == exception_date,
                CapacityException.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        start: date | None = None,
        end: date | None = None,
    ) -> list[CapacityException]:
        conditions = [
            CapacityException.agency_id == agency_id,
            CapacityException.user_id == user_id,
            CapacityException.deleted_at.is_(None),
        ]
        if start is not None:
            conditions.append(CapacityException.date >= start)
        if end is not None:
            conditions.append(CapacityException.date <= end)
        result = await self.db.execute(
            select(CapacityException).where(*conditions).order_by(CapacityException.date.asc())
        )
        return list(result.scalars().all())

    async def create(self, data: dict) -> CapacityException:
        obj = CapacityException(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, obj: CapacityException, data: dict) -> CapacityException:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        return obj

    async def soft_delete(self, obj: CapacityException) -> None:
        obj.soft_delete()
        await self.db.flush()

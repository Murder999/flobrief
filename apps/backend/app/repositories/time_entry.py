from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.time_entry import TimeEntry


class TimeEntryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_active_for_user(self, user_id: uuid.UUID) -> TimeEntry | None:
        result = await self.db.execute(
            select(TimeEntry).where(
                TimeEntry.user_id == user_id,
                TimeEntry.ended_at.is_(None),
                TimeEntry.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, entry_id: uuid.UUID, agency_id: uuid.UUID) -> TimeEntry | None:
        result = await self.db.execute(
            select(TimeEntry).where(
                TimeEntry.id == entry_id,
                TimeEntry.agency_id == agency_id,
                TimeEntry.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> TimeEntry:
        obj = TimeEntry(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def overlap_check(
        self,
        user_id: uuid.UUID,
        started_at: datetime,
        ended_at: datetime,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """True if [started_at, ended_at) overlaps any other completed entry
        for this user. Non-blocking — callers surface this as a warning."""
        stmt = select(TimeEntry.id).where(
            TimeEntry.user_id == user_id,
            TimeEntry.deleted_at.is_(None),
            TimeEntry.ended_at.is_not(None),
            TimeEntry.started_at < ended_at,
            TimeEntry.ended_at > started_at,
        )
        if exclude_id is not None:
            stmt = stmt.where(TimeEntry.id != exclude_id)
        result = await self.db.execute(stmt.limit(1))
        return result.scalar_one_or_none() is not None

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        agency_id: uuid.UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[TimeEntry]:
        conditions = [
            TimeEntry.user_id == user_id,
            TimeEntry.agency_id == agency_id,
            TimeEntry.deleted_at.is_(None),
        ]
        if start is not None:
            conditions.append(TimeEntry.started_at >= start)
        if end is not None:
            conditions.append(TimeEntry.started_at <= end)
        result = await self.db.execute(
            select(TimeEntry).where(*conditions).order_by(TimeEntry.started_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_brief(self, brief_id: uuid.UUID, agency_id: uuid.UUID) -> list[TimeEntry]:
        result = await self.db.execute(
            select(TimeEntry)
            .where(
                TimeEntry.brief_id == brief_id,
                TimeEntry.agency_id == agency_id,
                TimeEntry.deleted_at.is_(None),
            )
            .order_by(TimeEntry.started_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_brand(
        self,
        brand_id: uuid.UUID,
        agency_id: uuid.UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[TimeEntry]:
        conditions = [
            TimeEntry.brand_id == brand_id,
            TimeEntry.agency_id == agency_id,
            TimeEntry.deleted_at.is_(None),
        ]
        if start is not None:
            conditions.append(TimeEntry.started_at >= start)
        if end is not None:
            conditions.append(TimeEntry.started_at <= end)
        result = await self.db.execute(
            select(TimeEntry).where(*conditions).order_by(TimeEntry.started_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_agency(
        self,
        agency_id: uuid.UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[TimeEntry]:
        conditions = [
            TimeEntry.agency_id == agency_id,
            TimeEntry.deleted_at.is_(None),
        ]
        if start is not None:
            conditions.append(TimeEntry.started_at >= start)
        if end is not None:
            conditions.append(TimeEntry.started_at <= end)
        result = await self.db.execute(
            select(TimeEntry).where(*conditions).order_by(TimeEntry.started_at.asc())
        )
        return list(result.scalars().all())

    async def lock(self, entry: TimeEntry, locked_by_id: uuid.UUID) -> TimeEntry:
        entry.locked = True
        entry.locked_by_id = locked_by_id
        entry.locked_at = datetime.now(UTC)
        await self.db.flush()
        return entry

    async def update(self, entry: TimeEntry, data: dict) -> TimeEntry:
        for key, value in data.items():
            setattr(entry, key, value)
        await self.db.flush()
        return entry

    async def soft_delete(self, entry: TimeEntry) -> None:
        entry.deleted_at = datetime.now(UTC)
        await self.db.flush()

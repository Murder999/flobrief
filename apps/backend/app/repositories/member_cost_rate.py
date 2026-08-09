from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commercial_terms import MemberCostRate


class MemberCostRateRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, rate_id: uuid.UUID, agency_id: uuid.UUID) -> MemberCostRate | None:
        result = await self.db.execute(
            select(MemberCostRate).where(
                MemberCostRate.id == rate_id,
                MemberCostRate.agency_id == agency_id,
                MemberCostRate.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_open_ended_for_user(
        self, agency_id: uuid.UUID, user_id: uuid.UUID
    ) -> MemberCostRate | None:
        result = await self.db.execute(
            select(MemberCostRate).where(
                MemberCostRate.agency_id == agency_id,
                MemberCostRate.user_id == user_id,
                MemberCostRate.valid_until.is_(None),
                MemberCostRate.active.is_(True),
                MemberCostRate.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_open_ended_for_role(
        self, agency_id: uuid.UUID, role: str
    ) -> MemberCostRate | None:
        result = await self.db.execute(
            select(MemberCostRate).where(
                MemberCostRate.agency_id == agency_id,
                MemberCostRate.role == role,
                MemberCostRate.valid_until.is_(None),
                MemberCostRate.active.is_(True),
                MemberCostRate.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_effective_for_user(
        self, agency_id: uuid.UUID, user_id: uuid.UUID, as_of: date
    ) -> MemberCostRate | None:
        """The active user-specific rate covering `as_of` (open-ended or
        bounded) — used by `ClientInvoiceService.generate_draft` to snapshot
        `TimeEntry.cost_rate_snapshot_cents` at invoicing time (plan §3
        snapshot-timing decision). Ties broken by most recent `valid_from`."""
        result = await self.db.execute(
            select(MemberCostRate)
            .where(
                MemberCostRate.agency_id == agency_id,
                MemberCostRate.user_id == user_id,
                MemberCostRate.active.is_(True),
                MemberCostRate.deleted_at.is_(None),
                MemberCostRate.valid_from <= as_of,
                or_(MemberCostRate.valid_until.is_(None), MemberCostRate.valid_until >= as_of),
            )
            .order_by(MemberCostRate.valid_from.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_effective_for_role(
        self, agency_id: uuid.UUID, role: str, as_of: date
    ) -> MemberCostRate | None:
        result = await self.db.execute(
            select(MemberCostRate)
            .where(
                MemberCostRate.agency_id == agency_id,
                MemberCostRate.role == role,
                MemberCostRate.active.is_(True),
                MemberCostRate.deleted_at.is_(None),
                MemberCostRate.valid_from <= as_of,
                or_(MemberCostRate.valid_until.is_(None), MemberCostRate.valid_until >= as_of),
            )
            .order_by(MemberCostRate.valid_from.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, agency_id: uuid.UUID, user_id: uuid.UUID) -> list[MemberCostRate]:
        result = await self.db.execute(
            select(MemberCostRate)
            .where(
                MemberCostRate.agency_id == agency_id,
                MemberCostRate.user_id == user_id,
                MemberCostRate.deleted_at.is_(None),
            )
            .order_by(MemberCostRate.valid_from.desc())
        )
        return list(result.scalars().all())

    async def list_for_role(self, agency_id: uuid.UUID, role: str) -> list[MemberCostRate]:
        result = await self.db.execute(
            select(MemberCostRate)
            .where(
                MemberCostRate.agency_id == agency_id,
                MemberCostRate.role == role,
                MemberCostRate.deleted_at.is_(None),
            )
            .order_by(MemberCostRate.valid_from.desc())
        )
        return list(result.scalars().all())

    async def create(self, data: dict) -> MemberCostRate:
        obj = MemberCostRate(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, obj: MemberCostRate, data: dict) -> MemberCostRate:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        return obj

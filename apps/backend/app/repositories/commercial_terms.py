from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commercial_terms import CommercialTerms


class CommercialTermsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, terms_id: uuid.UUID, agency_id: uuid.UUID) -> CommercialTerms | None:
        result = await self.db.execute(
            select(CommercialTerms).where(
                CommercialTerms.id == terms_id,
                CommercialTerms.agency_id == agency_id,
                CommercialTerms.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_for_brand(
        self, agency_id: uuid.UUID, brand_id: uuid.UUID
    ) -> CommercialTerms | None:
        result = await self.db.execute(
            select(CommercialTerms).where(
                CommercialTerms.agency_id == agency_id,
                CommercialTerms.brand_id == brand_id,
                CommercialTerms.active.is_(True),
                CommercialTerms.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_brand(
        self, agency_id: uuid.UUID, brand_id: uuid.UUID
    ) -> list[CommercialTerms]:
        result = await self.db.execute(
            select(CommercialTerms)
            .where(
                CommercialTerms.agency_id == agency_id,
                CommercialTerms.brand_id == brand_id,
                CommercialTerms.deleted_at.is_(None),
            )
            .order_by(CommercialTerms.valid_from.desc())
        )
        return list(result.scalars().all())

    async def list_overlapping(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID,
        valid_from: date,
        valid_until: date | None,
        exclude_id: uuid.UUID | None = None,
    ) -> list[CommercialTerms]:
        """Rows whose [valid_from, valid_until] date range overlaps the given
        range for this brand. `valid_until IS NULL` means open-ended (never
        expires), so it overlaps anything on or after its `valid_from`."""
        conditions = [
            CommercialTerms.agency_id == agency_id,
            CommercialTerms.brand_id == brand_id,
            CommercialTerms.deleted_at.is_(None),
            CommercialTerms.valid_from <= (valid_until if valid_until is not None else date.max),
        ]
        result = await self.db.execute(select(CommercialTerms).where(*conditions))
        rows = list(result.scalars().all())

        def _overlaps(row: CommercialTerms) -> bool:
            if exclude_id is not None and row.id == exclude_id:
                return False
            row_end = row.valid_until or date.max
            other_end = valid_until or date.max
            return row.valid_from <= other_end and valid_from <= row_end

        return [r for r in rows if _overlaps(r)]

    async def create(self, data: dict) -> CommercialTerms:
        obj = CommercialTerms(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, obj: CommercialTerms, data: dict) -> CommercialTerms:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        return obj

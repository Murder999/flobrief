from __future__ import annotations

import re
import uuid as uuid_lib
from uuid import UUID

from sqlalchemy import select

from app.models.brand import Brand
from app.repositories.base import BaseRepository


def _make_base_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:90] if slug else "brand"


class BrandRepository(BaseRepository[Brand]):
    model = Brand

    async def list_by_agency(self, agency_id: UUID, *, limit: int = 100) -> list[Brand]:
        stmt = (
            select(Brand)
            .where(
                Brand.agency_id == agency_id,
                Brand.deleted_at.is_(None),
            )
            .order_by(Brand.name)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_slug_and_agency(self, slug: str, agency_id: UUID) -> Brand | None:
        stmt = select(Brand).where(
            Brand.slug == slug,
            Brand.agency_id == agency_id,
            Brand.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_and_agency(self, brand_id: UUID, agency_id: UUID) -> Brand | None:
        """Tenant-scoped lookup. Returns None if brand does not belong to agency."""
        stmt = select(Brand).where(
            Brand.id == brand_id,
            Brand.agency_id == agency_id,
            Brand.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def slug_exists_in_agency(self, slug: str, agency_id: UUID) -> bool:
        return await self.get_by_slug_and_agency(slug, agency_id) is not None

    async def generate_unique_slug(self, name: str, agency_id: UUID) -> str:
        base = _make_base_slug(name)
        slug = base
        while await self.slug_exists_in_agency(slug, agency_id):
            suffix = uuid_lib.uuid4().hex[:6]
            slug = f"{base}-{suffix}"
        return slug

    async def list_for_user(self, user_id: UUID) -> list[Brand]:
        from app.models.brand_member import BrandMember

        stmt = (
            select(Brand)
            .join(BrandMember, BrandMember.brand_id == Brand.id)
            .where(
                BrandMember.user_id == user_id,
                BrandMember.deleted_at.is_(None),
                Brand.deleted_at.is_(None),
            )
            .order_by(Brand.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

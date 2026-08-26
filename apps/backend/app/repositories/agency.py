from __future__ import annotations

import re
import uuid as uuid_lib
from uuid import UUID

from sqlalchemy import select

from app.models.agency import Agency
from app.repositories.base import BaseRepository


def _make_base_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:90] if slug else "agency"


class AgencyRepository(BaseRepository[Agency]):
    model = Agency

    async def get_by_slug(self, slug: str) -> Agency | None:
        stmt = select(Agency).where(
            Agency.slug == slug,
            Agency.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        return await self.get_by_slug(slug) is not None

    async def generate_unique_slug(self, name: str) -> str:
        base = _make_base_slug(name)
        slug = base
        while await self.slug_exists(slug):
            suffix = uuid_lib.uuid4().hex[:6]
            slug = f"{base}-{suffix}"
        return slug

    async def list_by_owner(self, owner_user_id: UUID) -> list[Agency]:
        stmt = (
            select(Agency)
            .where(
                Agency.owner_user_id == owner_user_id,
                Agency.deleted_at.is_(None),
            )
            .order_by(Agency.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_user(self, user_id: UUID) -> list[Agency]:
        from app.models.agency_member import AgencyMember

        stmt = (
            select(Agency)
            .join(AgencyMember, AgencyMember.agency_id == Agency.id)
            .where(
                AgencyMember.user_id == user_id,
                AgencyMember.status == "active",
                AgencyMember.deleted_at.is_(None),
                Agency.deleted_at.is_(None),
                Agency.status == "active",
            )
            .order_by(Agency.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

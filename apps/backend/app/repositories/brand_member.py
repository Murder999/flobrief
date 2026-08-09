from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand_member import BrandMember
from app.models.enums import BrandMemberStatus
from app.repositories.base import BaseRepository


class BrandMemberRepository(BaseRepository[BrandMember]):
    model = BrandMember

    async def get_membership(self, brand_id: UUID, user_id: UUID) -> BrandMember | None:
        stmt = select(BrandMember).where(
            BrandMember.brand_id == brand_id,
            BrandMember.user_id == user_id,
            BrandMember.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_brand(self, brand_id: UUID) -> list[BrandMember]:
        stmt = (
            select(BrandMember)
            .where(
                BrandMember.brand_id == brand_id,
                BrandMember.deleted_at.is_(None),
            )
            .order_by(BrandMember.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_user(self, user_id: UUID) -> list[BrandMember]:
        stmt = select(BrandMember).where(
            BrandMember.user_id == user_id,
            BrandMember.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def is_member(self, brand_id: UUID, user_id: UUID) -> bool:
        member = await self.get_membership(brand_id, user_id)
        return member is not None and member.status == BrandMemberStatus.ACTIVE.value

    @staticmethod
    def _new(session: AsyncSession) -> BrandMemberRepository:
        return BrandMemberRepository(session)

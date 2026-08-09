from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberStatus
from app.repositories.base import BaseRepository


class AgencyMemberRepository(BaseRepository[AgencyMember]):
    model = AgencyMember

    async def get_membership(self, agency_id: UUID, user_id: UUID) -> AgencyMember | None:
        stmt = select(AgencyMember).where(
            AgencyMember.agency_id == agency_id,
            AgencyMember.user_id == user_id,
            AgencyMember.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_agency(self, agency_id: UUID) -> list[AgencyMember]:
        stmt = (
            select(AgencyMember)
            .where(
                AgencyMember.agency_id == agency_id,
                AgencyMember.deleted_at.is_(None),
            )
            .order_by(AgencyMember.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_user(self, user_id: UUID) -> list[AgencyMember]:
        stmt = select(AgencyMember).where(
            AgencyMember.user_id == user_id,
            AgencyMember.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def is_member(self, agency_id: UUID, user_id: UUID) -> bool:
        member = await self.get_membership(agency_id, user_id)
        return member is not None and member.status == AgencyMemberStatus.ACTIVE.value

    async def count_owners(self, agency_id: UUID) -> int:
        from app.models.enums import AgencyMemberRole

        stmt = select(AgencyMember).where(
            AgencyMember.agency_id == agency_id,
            AgencyMember.role == AgencyMemberRole.OWNER.value,
            AgencyMember.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    @staticmethod
    def _new(session: AsyncSession) -> AgencyMemberRepository:
        return AgencyMemberRepository(session)

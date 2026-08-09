from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, AgencyStatus
from app.models.user import User
from app.repositories.agency import AgencyRepository
from app.repositories.agency_member import AgencyMemberRepository
from app.schemas.agency import AgencyCreate, AgencyMemberRoleUpdate, AgencyUpdate

_403 = status.HTTP_403_FORBIDDEN
_404 = status.HTTP_404_NOT_FOUND
_409 = status.HTTP_409_CONFLICT


class AgencyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.agency_repo = AgencyRepository(db)
        self.member_repo = AgencyMemberRepository(db)

    async def create_agency(self, data: AgencyCreate, owner: User) -> Agency:
        if owner.is_platform_admin:
            raise HTTPException(_403, "platform_admin cannot create agencies")

        if data.slug:
            if await self.agency_repo.slug_exists(data.slug):
                raise HTTPException(_409, "Bu slug zaten kullanımda")
            slug = data.slug
        else:
            slug = await self.agency_repo.generate_unique_slug(data.name)

        agency = await self.agency_repo.create(
            name=data.name,
            slug=slug,
            status=AgencyStatus.ACTIVE.value,
            owner_user_id=owner.id,
        )

        await self.member_repo.create(
            agency_id=agency.id,
            user_id=owner.id,
            role=AgencyMemberRole.OWNER.value,
            status=AgencyMemberStatus.ACTIVE.value,
            joined_at=datetime.now(UTC),
        )

        await self.db.commit()
        await self.db.refresh(agency)
        return agency

    async def get_agency_for_user(
        self, agency_id: uuid.UUID, user: User
    ) -> tuple[Agency, AgencyMember]:
        """Returns (agency, membership). Enforces tenant isolation."""
        agency = await self.agency_repo.get_by_id(agency_id)
        if agency is None:
            raise HTTPException(_404, "Agency bulunamadı")

        member = await self.member_repo.get_membership(agency_id, user.id)
        if member is None:
            raise HTTPException(_403, "Bu agency'ye erişim yetkiniz yok")

        return agency, member

    async def update_agency(
        self,
        agency_id: uuid.UUID,
        data: AgencyUpdate,
        user: User,
    ) -> Agency:
        agency, member = await self.get_agency_for_user(agency_id, user)
        _require_role(member, {AgencyMemberRole.OWNER.value, AgencyMemberRole.ADMIN.value})

        updates: dict[str, object] = {}
        if data.name is not None:
            updates["name"] = data.name

        if not updates:
            return agency

        await self.agency_repo.update(agency, **updates)
        await self.db.commit()
        await self.db.refresh(agency)
        return agency

    async def list_members(self, agency_id: uuid.UUID, user: User) -> list[AgencyMember]:
        _, _ = await self.get_agency_for_user(agency_id, user)
        return await self.member_repo.list_by_agency(agency_id)

    async def update_member_role(
        self,
        agency_id: uuid.UUID,
        target_user_id: uuid.UUID,
        data: AgencyMemberRoleUpdate,
        actor: User,
    ) -> AgencyMember:
        _, actor_member = await self.get_agency_for_user(agency_id, actor)
        _require_role(actor_member, {AgencyMemberRole.OWNER.value})

        target = await self.member_repo.get_membership(agency_id, target_user_id)
        if target is None:
            raise HTTPException(_404, "Üye bulunamadı")
        if target.role == AgencyMemberRole.OWNER.value:
            raise HTTPException(_409, "Agency owner rolü değiştirilemez")

        await self.member_repo.update(target, role=data.role)
        await self.db.commit()
        await self.db.refresh(target)
        return target

    async def remove_member(
        self,
        agency_id: uuid.UUID,
        target_user_id: uuid.UUID,
        actor: User,
    ) -> None:
        _, actor_member = await self.get_agency_for_user(agency_id, actor)
        _require_role(actor_member, {AgencyMemberRole.OWNER.value, AgencyMemberRole.ADMIN.value})

        target = await self.member_repo.get_membership(agency_id, target_user_id)
        if target is None:
            raise HTTPException(_404, "Üye bulunamadı")
        if target.role == AgencyMemberRole.OWNER.value:
            raise HTTPException(_409, "Agency owner kaldırılamaz")
        if str(target_user_id) == str(actor.id):
            raise HTTPException(_409, "Kendinizi kaldıramazsınız")

        await self.member_repo.soft_delete(target)
        await self.db.commit()


def _require_role(member: AgencyMember, allowed: set[str]) -> None:
    if member.role not in allowed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Bu işlem için gereken rol: {sorted(allowed)}",
        )

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.enums import AgencyMemberRole, BrandStatus
from app.models.user import User
from app.repositories.activity import ActivityLogRepository
from app.repositories.agency_member import AgencyMemberRepository
from app.repositories.brand import BrandRepository
from app.repositories.brand_member import BrandMemberRepository
from app.schemas.brand import BrandCreate, BrandMemberRoleUpdate, BrandUpdate
from app.services.entitlement_service import EntitlementService

_403 = status.HTTP_403_FORBIDDEN
_404 = status.HTTP_404_NOT_FOUND
_409 = status.HTTP_409_CONFLICT


class BrandService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.brand_repo = BrandRepository(db)
        self.brand_member_repo = BrandMemberRepository(db)
        self.agency_member_repo = AgencyMemberRepository(db)
        self._activity = ActivityLogRepository(db)

    async def create_brand(self, agency_id: uuid.UUID, data: BrandCreate, actor: User) -> Brand:
        agency_member = await self.agency_member_repo.get_membership(agency_id, actor.id)
        if agency_member is None:
            raise HTTPException(_403, "Bu agency'ye erişim yetkiniz yok")

        allowed = {
            AgencyMemberRole.OWNER.value,
            AgencyMemberRole.ADMIN.value,
            AgencyMemberRole.BRAND_MANAGER.value,
        }
        if agency_member.role not in allowed:
            raise HTTPException(_403, "Marka oluşturma yetkiniz yok")

        await EntitlementService(self.db).check_brand_limit(agency_id)

        if data.slug:
            if await self.brand_repo.slug_exists_in_agency(data.slug, agency_id):
                raise HTTPException(_409, "Bu slug bu agency'de zaten kullanımda")
            slug = data.slug
        else:
            slug = await self.brand_repo.generate_unique_slug(data.name, agency_id)

        brand = await self.brand_repo.create(
            name=data.name,
            slug=slug,
            agency_id=agency_id,
            status=BrandStatus.ACTIVE.value,
        )
        await self._activity.create(
            action="brand.created",
            entity_type="brand",
            entity_id=brand.id,
            agency_id=agency_id,
            brand_id=brand.id,
            actor_user_id=actor.id,
            meta={"name": data.name},
        )
        await self.db.commit()
        await self.db.refresh(brand)
        return brand

    async def get_brand_for_agency(
        self, brand_id: uuid.UUID, agency_id: uuid.UUID, user: User
    ) -> Brand:
        """Tenant-scoped brand lookup. Enforces that brand belongs to agency."""
        agency_member = await self.agency_member_repo.get_membership(agency_id, user.id)
        brand_member = await self.brand_member_repo.get_membership(brand_id, user.id)

        if agency_member is None and brand_member is None:
            raise HTTPException(_403, "Bu markaya erişim yetkiniz yok")

        brand = await self.brand_repo.get_by_id_and_agency(brand_id, agency_id)
        if brand is None:
            raise HTTPException(_404, "Marka bulunamadı veya bu agency'ye ait değil")

        return brand

    async def update_brand(
        self,
        brand_id: uuid.UUID,
        agency_id: uuid.UUID,
        data: BrandUpdate,
        actor: User,
    ) -> Brand:
        brand = await self.get_brand_for_agency(brand_id, agency_id, actor)
        agency_member = await self.agency_member_repo.get_membership(agency_id, actor.id)

        allowed = {
            AgencyMemberRole.OWNER.value,
            AgencyMemberRole.ADMIN.value,
            AgencyMemberRole.BRAND_MANAGER.value,
        }
        if agency_member is None or agency_member.role not in allowed:
            raise HTTPException(_403, "Marka güncelleme yetkiniz yok")

        updates: dict[str, object] = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.status is not None:
            updates["status"] = data.status.value

        if not updates:
            return brand

        await self.brand_repo.update(brand, **updates)
        await self.db.commit()
        await self.db.refresh(brand)
        return brand

    async def list_brands_for_agency(self, agency_id: uuid.UUID, user: User) -> list[Brand]:
        agency_member = await self.agency_member_repo.get_membership(agency_id, user.id)
        if agency_member is None:
            raise HTTPException(_403, "Bu agency'ye erişim yetkiniz yok")
        return await self.brand_repo.list_by_agency(agency_id)

    async def list_members(
        self, brand_id: uuid.UUID, agency_id: uuid.UUID, user: User
    ) -> list[BrandMember]:
        await self.get_brand_for_agency(brand_id, agency_id, user)
        return await self.brand_member_repo.list_by_brand(brand_id)

    async def update_member_role(
        self,
        brand_id: uuid.UUID,
        agency_id: uuid.UUID,
        target_user_id: uuid.UUID,
        data: BrandMemberRoleUpdate,
        actor: User,
    ) -> BrandMember:
        await self.get_brand_for_agency(brand_id, agency_id, actor)
        agency_member = await self.agency_member_repo.get_membership(agency_id, actor.id)
        allowed = {AgencyMemberRole.OWNER.value, AgencyMemberRole.ADMIN.value}
        if agency_member is None or agency_member.role not in allowed:
            raise HTTPException(_403, "Üye rolü değiştirme yetkiniz yok")

        target = await self.brand_member_repo.get_membership(brand_id, target_user_id)
        if target is None:
            raise HTTPException(_404, "Üye bulunamadı")

        await self.brand_member_repo.update(target, role=data.role)
        await self.db.commit()
        await self.db.refresh(target)
        return target

    async def remove_member(
        self,
        brand_id: uuid.UUID,
        agency_id: uuid.UUID,
        target_user_id: uuid.UUID,
        actor: User,
    ) -> None:
        await self.get_brand_for_agency(brand_id, agency_id, actor)
        agency_member = await self.agency_member_repo.get_membership(agency_id, actor.id)
        allowed = {AgencyMemberRole.OWNER.value, AgencyMemberRole.ADMIN.value}
        if agency_member is None or agency_member.role not in allowed:
            raise HTTPException(_403, "Üye kaldırma yetkiniz yok")

        target = await self.brand_member_repo.get_membership(brand_id, target_user_id)
        if target is None:
            raise HTTPException(_404, "Üye bulunamadı")

        await self.brand_member_repo.soft_delete(target)
        await self.db.commit()

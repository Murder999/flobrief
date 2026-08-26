from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import require_verified
from app.core.rbac import Permission, get_permissions_for_brand_role
from app.db.session import get_db
from app.models.agency import Agency
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.enums import AgencyStatus, BrandMemberStatus, UserType
from app.models.user import User
from app.services.demo_access import enforce_demo_workspace_request


@dataclass
class BrandPortalContext:
    user: User
    brand: Brand
    membership: BrandMember

    @property
    def is_manager(self) -> bool:
        return self.membership.role in ("brand_owner", "brand_manager")

    @property
    def permissions(self) -> frozenset[Permission]:
        return get_permissions_for_brand_role(self.membership.role)

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions


async def get_brand_portal_context(
    request: Request,
    x_brand_id: str | None = Header(default=None, alias="X-Brand-ID"),
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> BrandPortalContext:
    """Resolve an exact active brand membership for the requested workspace."""
    if current_user.user_type == UserType.PLATFORM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="platform_admin brand portalına erişemez",
        )

    membership_query = select(BrandMember).where(
        BrandMember.user_id == current_user.id,
        BrandMember.status == BrandMemberStatus.ACTIVE.value,
        BrandMember.deleted_at.is_(None),
    )
    if x_brand_id:
        try:
            brand_id = UUID(x_brand_id)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Geçersiz X-Brand-ID formatı",
            ) from err
        membership_query = membership_query.where(BrandMember.brand_id == brand_id)
        membership = (await db.execute(membership_query)).scalar_one_or_none()
    else:
        memberships = list((await db.execute(membership_query.limit(2))).scalars().all())
        if len(memberships) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Birden fazla marka üyeliği için X-Brand-ID başlığı gerekli",
            )
        membership = memberships[0] if memberships else None

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu marka için aktif üyeliğiniz bulunmuyor",
        )

    brand_result = await db.execute(
        select(Brand).where(
            Brand.id == membership.brand_id,
            Brand.status == "active",
            Brand.deleted_at.is_(None),
        )
    )
    brand = brand_result.scalar_one_or_none()

    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Markanız bulunamadı",
        )

    if brand.agency_id is not None:
        agency = await db.scalar(
            select(Agency).where(
                Agency.id == brand.agency_id,
                Agency.status == AgencyStatus.ACTIVE.value,
                Agency.deleted_at.is_(None),
            )
        )
        if agency is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ajans bulunamadı")
        enforce_demo_workspace_request(agency, request)

    return BrandPortalContext(user=current_user, brand=brand, membership=membership)

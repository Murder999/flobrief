from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import require_verified
from app.core.rbac import Permission, get_permissions_for_brand_role
from app.db.session import get_db
from app.models.agency import Agency
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.enums import BrandMemberStatus, UserType
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
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> BrandPortalContext:
    """Resolves brand portal context from authenticated brand_user JWT.

    Does NOT require X-Agency-ID header. Brand users access data scoped
    to their brand membership only — no agency workspace needed.
    """
    if current_user.user_type == UserType.PLATFORM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="platform_admin brand portalına erişemez",
        )

    if current_user.user_type == UserType.AGENCY_USER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ajans kullanıcıları brand portalına erişemez",
        )

    # Find the user's active brand membership
    result = await db.execute(
        select(BrandMember).where(
            BrandMember.user_id == current_user.id,
            BrandMember.status == BrandMemberStatus.ACTIVE.value,
            BrandMember.deleted_at.is_(None),
        )
    )
    membership = result.scalars().first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aktif bir marka üyeliğiniz bulunmuyor",
        )

    brand_result = await db.execute(
        select(Brand).where(
            Brand.id == membership.brand_id,
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
                Agency.deleted_at.is_(None),
            )
        )
        if agency is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ajans bulunamadı")
        enforce_demo_workspace_request(agency, request)

    return BrandPortalContext(user=current_user, brand=brand, membership=membership)

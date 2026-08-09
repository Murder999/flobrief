"""Platform admin — brand management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_platform_admin_user
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.models.agency import Agency
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.brief import Brief
from app.models.user import User
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.schemas.brand_identity import (
    BrandIdentityOverview,
    BrandIdentityProfileRead,
    BrandIdentityProfileUpdate,
)
from app.schemas.platform import (
    PlatformBrandMemberRead,
    PlatformBrandRead,
    PlatformBrandUpdate,
)

platform_brands_router = APIRouter(prefix="/brands", tags=["platform-brands"])


async def _count_brand_members(db: AsyncSession, brand_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(BrandMember)
        .where(BrandMember.brand_id == brand_id, BrandMember.deleted_at.is_(None))
    )
    return result.scalar_one()


async def _count_brand_briefs(db: AsyncSession, brand_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Brief)
        .where(Brief.brand_id == brand_id, Brief.deleted_at.is_(None))
    )
    return result.scalar_one()


async def _get_agency_name(db: AsyncSession, agency_id: uuid.UUID | None) -> str | None:
    if agency_id is None:
        return None
    result = await db.execute(
        select(Agency.name).where(Agency.id == agency_id, Agency.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


@platform_brands_router.get("", response_model=list[PlatformBrandRead])
async def list_brands(
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    status_filter: str | None = None,
    agency_id: uuid.UUID | None = None,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformBrandRead]:
    demo_agency = select(Agency.id).where(
        Agency.id == Brand.agency_id,
        Agency.deleted_at.is_(None),
        Agency.is_demo.is_(True),
    )
    stmt = (
        select(Brand)
        .where(Brand.deleted_at.is_(None), ~exists(demo_agency))
        .order_by(Brand.created_at.desc())
    )
    if search:
        stmt = stmt.where(Brand.name.ilike(f"%{search}%"))
    if status_filter:
        stmt = stmt.where(Brand.status == status_filter)
    if agency_id:
        stmt = stmt.where(Brand.agency_id == agency_id)
    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    brands = result.scalars().all()

    out = []
    for br in brands:
        out.append(
            PlatformBrandRead(
                id=br.id,
                name=br.name,
                slug=br.slug,
                status=br.status,
                agency_id=br.agency_id,
                agency_name=await _get_agency_name(db, br.agency_id),
                member_count=await _count_brand_members(db, br.id),
                brief_count=await _count_brand_briefs(db, br.id),
                created_at=br.created_at,
                updated_at=br.updated_at,
            )
        )
    return out


@platform_brands_router.get("/{brand_id}", response_model=PlatformBrandRead)
async def get_brand_detail(
    brand_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformBrandRead:
    result = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.deleted_at.is_(None)))
    br = result.scalar_one_or_none()
    if br is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    return PlatformBrandRead(
        id=br.id,
        name=br.name,
        slug=br.slug,
        status=br.status,
        agency_id=br.agency_id,
        agency_name=await _get_agency_name(db, br.agency_id),
        member_count=await _count_brand_members(db, br.id),
        brief_count=await _count_brand_briefs(db, br.id),
        created_at=br.created_at,
        updated_at=br.updated_at,
    )


@platform_brands_router.patch("/{brand_id}", response_model=PlatformBrandRead)
async def update_brand(
    brand_id: uuid.UUID,
    body: PlatformBrandUpdate,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformBrandRead:
    result = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.deleted_at.is_(None)))
    br = result.scalar_one_or_none()
    if br is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    changed: dict = {}
    if body.name is not None:
        changed["name"] = body.name
        br.name = body.name
    if body.status is not None:
        changed["status"] = body.status
        br.status = body.status

    db.add(br)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="brand.updated",
        target_type="brand",
        target_id=brand_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"changed": changed},
    )
    await db.commit()
    await db.refresh(br)

    return PlatformBrandRead(
        id=br.id,
        name=br.name,
        slug=br.slug,
        status=br.status,
        agency_id=br.agency_id,
        agency_name=await _get_agency_name(db, br.agency_id),
        member_count=await _count_brand_members(db, br.id),
        brief_count=await _count_brand_briefs(db, br.id),
        created_at=br.created_at,
        updated_at=br.updated_at,
    )


@platform_brands_router.get("/{brand_id}/members", response_model=list[PlatformBrandMemberRead])
async def list_brand_members(
    brand_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformBrandMemberRead]:
    result = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.deleted_at.is_(None)))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    members_result = await db.execute(
        select(BrandMember, User)
        .join(User, User.id == BrandMember.user_id)
        .where(
            BrandMember.brand_id == brand_id,
            BrandMember.deleted_at.is_(None),
        )
        .order_by(BrandMember.created_at.asc())
    )
    return [
        PlatformBrandMemberRead(
            id=bm.id,
            user_id=bm.user_id,
            user_email=u.email,
            user_full_name=u.full_name,
            role=bm.role,
            status=bm.status,
            joined_at=bm.joined_at,
            created_at=bm.created_at,
        )
        for bm, u in members_result.all()
    ]


@platform_brands_router.get("/{brand_id}/briefs")
async def list_brand_briefs(
    brand_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.deleted_at.is_(None)))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    briefs_result = await db.execute(
        select(Brief)
        .where(Brief.brand_id == brand_id, Brief.deleted_at.is_(None))
        .order_by(Brief.created_at.desc())
        .limit(100)
    )
    briefs = briefs_result.scalars().all()

    # Count by status
    status_counts: dict[str, int] = {}
    for br_item in briefs:
        status_counts[br_item.status] = status_counts.get(br_item.status, 0) + 1

    return [
        {
            "id": str(b.id),
            "title": b.title,
            "status": b.status,
            "priority": b.priority,
            "created_at": b.created_at.isoformat(),
        }
        for b in briefs
    ]


# ── Platform admin: Marka DNA endpoints ──────────────────────────────────────


@platform_brands_router.get("/{brand_id}/identity", response_model=BrandIdentityOverview)
async def platform_get_brand_identity(
    brand_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> BrandIdentityOverview:
    from app.services.brand_identity_service import BrandIdentityService

    svc = BrandIdentityService(db)
    return await svc.get_overview(brand_id, None, platform_admin=True)


@platform_brands_router.patch(
    "/{brand_id}/identity/profile",
    response_model=BrandIdentityProfileRead,
)
async def platform_update_brand_identity_profile(
    brand_id: uuid.UUID,
    data: BrandIdentityProfileUpdate,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> BrandIdentityProfileRead:
    from app.services.brand_identity_service import BrandIdentityService

    svc = BrandIdentityService(db)
    return await svc.update_profile(brand_id, None, data, admin)


@platform_brands_router.post(
    "/{brand_id}/identity/profile/approve",
    response_model=BrandIdentityProfileRead,
)
async def platform_approve_brand_identity_profile(
    brand_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> BrandIdentityProfileRead:
    from app.services.brand_identity_service import BrandIdentityService

    svc = BrandIdentityService(db)
    return await svc.approve_profile(brand_id, None, admin)

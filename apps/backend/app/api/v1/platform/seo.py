"""Platform admin — SEO, growth settings, and metrics endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_platform_admin_user
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.models.agency import Agency
from app.models.brand import Brand
from app.models.brief import Brief
from app.models.enums import UserType
from app.models.platform_seo_settings import PlatformGrowthSettings, PlatformSeoPageSettings
from app.models.user import User
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.schemas.platform import (
    PlatformGrowthMetrics,
    PlatformGrowthSettingsRead,
    PlatformGrowthSettingsUpdate,
    PlatformIntegrationStatus,
    PlatformPageSpeedResult,
    PlatformRobotsUpdate,
    PlatformSeoAuditIssue,
    PlatformSeoHealthSummary,
    PlatformSeoPageInventoryItem,
    PlatformSeoPageRead,
    PlatformSeoPageUpdate,
)
from app.services import pagespeed_service, seo_audit_service

platform_seo_router = APIRouter(prefix="/seo", tags=["platform-seo"])
platform_growth_router = APIRouter(prefix="/growth", tags=["platform-growth"])


@platform_seo_router.get("/audit", response_model=list[PlatformSeoAuditIssue])
async def get_seo_audit(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformSeoAuditIssue]:
    return await seo_audit_service.run_audit(db)


@platform_seo_router.get("/pages/inventory", response_model=list[PlatformSeoPageInventoryItem])
async def get_seo_page_inventory(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformSeoPageInventoryItem]:
    return await seo_audit_service.build_page_inventory(db)


@platform_seo_router.get("/health", response_model=PlatformSeoHealthSummary)
async def get_seo_health(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformSeoHealthSummary:
    return await seo_audit_service.build_health_summary(db)


# ── PageSpeed Insights (real integration, env-key gated) ──────────────────────


@platform_seo_router.get("/pagespeed", response_model=PlatformPageSpeedResult)
async def get_pagespeed_result(
    url: str,
    strategy: str = "mobile",
    admin: User = Depends(get_platform_admin_user),
) -> PlatformPageSpeedResult:
    try:
        result = await pagespeed_service.run_pagespeed_check(url, strategy)
    except pagespeed_service.PageSpeedNotConfiguredError as err:
        raise HTTPException(
            status_code=409,
            detail="PAGESPEED_API_KEY tanımlı değil. Kurulum kartından devam edin.",
        ) from err
    except pagespeed_service.PageSpeedApiError as err:
        raise HTTPException(status_code=err.status_code, detail=str(err)) from err
    return PlatformPageSpeedResult(**result)


# ── Integration setup-state (no OAuth flow — credential/env based, honest states) ──


@platform_seo_router.get("/integrations/pagespeed", response_model=PlatformIntegrationStatus)
async def get_pagespeed_integration_status(
    admin: User = Depends(get_platform_admin_user),
) -> PlatformIntegrationStatus:
    configured = pagespeed_service.is_pagespeed_configured()
    return PlatformIntegrationStatus(
        provider="pagespeed",
        configured=configured,
        detail={"required_env": "PAGESPEED_API_KEY"} if not configured else {},
    )


@platform_seo_router.get("/integrations/search-console", response_model=PlatformIntegrationStatus)
async def get_search_console_integration_status(
    admin: User = Depends(get_platform_admin_user),
) -> PlatformIntegrationStatus:
    configured = bool(
        settings.GOOGLE_SEARCH_CONSOLE_PROPERTY_URL
        and settings.GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_EMAIL
    )
    return PlatformIntegrationStatus(
        provider="search_console",
        configured=configured,
        detail=(
            {"property_url": settings.GOOGLE_SEARCH_CONSOLE_PROPERTY_URL}
            if configured
            else {
                "required_env": (
                    "GOOGLE_SEARCH_CONSOLE_PROPERTY_URL, "
                    "GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_EMAIL"
                ),
                "instructions": (
                    "Search Console mülkünüze bir servis hesabı e-postasını "
                    "'Tam' yetkiyle kullanıcı olarak ekleyin, ardından bu servis "
                    "hesabının kimlik bilgilerini backend ortam değişkenlerine tanımlayın."
                ),
            }
        ),
    )


@platform_seo_router.get("/integrations/ga4", response_model=PlatformIntegrationStatus)
async def get_ga4_integration_status(
    admin: User = Depends(get_platform_admin_user),
) -> PlatformIntegrationStatus:
    configured = bool(settings.GA4_PROPERTY_ID and settings.GA4_SERVICE_ACCOUNT_EMAIL)
    return PlatformIntegrationStatus(
        provider="ga4",
        configured=configured,
        detail=(
            {"property_id": settings.GA4_PROPERTY_ID}
            if configured
            else {
                "required_env": "GA4_PROPERTY_ID, GA4_SERVICE_ACCOUNT_EMAIL",
                "instructions": (
                    "GA4 mülkünüzde servis hesabına 'Görüntüleyici' erişimi verin, "
                    "ardından mülk kimliğini ve servis hesabı e-postasını backend "
                    "ortam değişkenlerine tanımlayın."
                ),
            }
        ),
    )


# ── SEO page settings ─────────────────────────────────────────────────────────


@platform_seo_router.get("/pages", response_model=list[PlatformSeoPageRead])
async def list_seo_pages(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformSeoPageRead]:
    result = await db.execute(
        select(PlatformSeoPageSettings)
        .where(PlatformSeoPageSettings.deleted_at.is_(None))
        .order_by(PlatformSeoPageSettings.page_key.asc())
    )
    pages = result.scalars().all()
    return [
        PlatformSeoPageRead(
            id=p.id,
            page_key=p.page_key,
            title=p.title,
            description=p.description,
            canonical_url=p.canonical_url,
            og_title=p.og_title,
            og_description=p.og_description,
            og_image_url=p.og_image_url,
            twitter_title=p.twitter_title,
            twitter_description=p.twitter_description,
            indexable=p.indexable,
            follow_links=p.follow_links,
            updated_at=p.updated_at,
        )
        for p in pages
    ]


@platform_seo_router.get("/pages/{page_key}", response_model=PlatformSeoPageRead)
async def get_seo_page(
    page_key: str,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformSeoPageRead:
    result = await db.execute(
        select(PlatformSeoPageSettings).where(
            PlatformSeoPageSettings.page_key == page_key,
            PlatformSeoPageSettings.deleted_at.is_(None),
        )
    )
    page = result.scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail="SEO page settings not found")

    return PlatformSeoPageRead(
        id=page.id,
        page_key=page.page_key,
        title=page.title,
        description=page.description,
        canonical_url=page.canonical_url,
        og_title=page.og_title,
        og_description=page.og_description,
        og_image_url=page.og_image_url,
        twitter_title=page.twitter_title,
        twitter_description=page.twitter_description,
        indexable=page.indexable,
        follow_links=page.follow_links,
        updated_at=page.updated_at,
    )


@platform_seo_router.patch("/pages/{page_key}", response_model=PlatformSeoPageRead)
async def upsert_seo_page(
    page_key: str,
    body: PlatformSeoPageUpdate,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformSeoPageRead:
    result = await db.execute(
        select(PlatformSeoPageSettings).where(
            PlatformSeoPageSettings.page_key == page_key,
            PlatformSeoPageSettings.deleted_at.is_(None),
        )
    )
    page = result.scalar_one_or_none()
    if page is None:
        page = PlatformSeoPageSettings(page_key=page_key)
        db.add(page)

    if body.title is not None:
        page.title = body.title
    if body.description is not None:
        page.description = body.description
    if body.canonical_url is not None:
        page.canonical_url = body.canonical_url
    if body.og_title is not None:
        page.og_title = body.og_title
    if body.og_description is not None:
        page.og_description = body.og_description
    if body.og_image_url is not None:
        page.og_image_url = body.og_image_url
    if body.twitter_title is not None:
        page.twitter_title = body.twitter_title
    if body.twitter_description is not None:
        page.twitter_description = body.twitter_description
    if body.indexable is not None:
        page.indexable = body.indexable
    if body.follow_links is not None:
        page.follow_links = body.follow_links

    db.add(page)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="seo.page_updated",
        target_type="seo_page",
        target_id=None,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"page_key": page_key},
    )
    await db.commit()
    await db.refresh(page)

    return PlatformSeoPageRead(
        id=page.id,
        page_key=page.page_key,
        title=page.title,
        description=page.description,
        canonical_url=page.canonical_url,
        og_title=page.og_title,
        og_description=page.og_description,
        og_image_url=page.og_image_url,
        twitter_title=page.twitter_title,
        twitter_description=page.twitter_description,
        indexable=page.indexable,
        follow_links=page.follow_links,
        updated_at=page.updated_at,
    )


# ── Growth / tracking settings ────────────────────────────────────────────────


async def _get_or_create_growth_settings(db: AsyncSession) -> PlatformGrowthSettings:
    result = await db.execute(
        select(PlatformGrowthSettings).where(
            PlatformGrowthSettings.setting_key == "default",
            PlatformGrowthSettings.deleted_at.is_(None),
        )
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = PlatformGrowthSettings(setting_key="default")
        db.add(settings)
        await db.flush()
    return settings


@platform_seo_router.get("/tracking", response_model=PlatformGrowthSettingsRead)
async def get_tracking_settings(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformGrowthSettingsRead:
    settings = await _get_or_create_growth_settings(db)
    await db.commit()
    return PlatformGrowthSettingsRead(
        google_analytics_id=settings.google_analytics_id,
        google_tag_manager_id=settings.google_tag_manager_id,
        search_console_verification=settings.search_console_verification,
        meta_pixel_id=settings.meta_pixel_id,
        linkedin_partner_id=settings.linkedin_partner_id,
        robots_txt=settings.robots_txt,
        sitemap_last_generated_at=settings.sitemap_last_generated_at,
        public_app_url=settings.public_app_url,
    )


@platform_seo_router.patch("/tracking", response_model=PlatformGrowthSettingsRead)
async def update_tracking_settings(
    body: PlatformGrowthSettingsUpdate,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformGrowthSettingsRead:
    settings = await _get_or_create_growth_settings(db)

    if body.google_analytics_id is not None:
        settings.google_analytics_id = body.google_analytics_id
    if body.google_tag_manager_id is not None:
        settings.google_tag_manager_id = body.google_tag_manager_id
    if body.search_console_verification is not None:
        settings.search_console_verification = body.search_console_verification
    if body.meta_pixel_id is not None:
        settings.meta_pixel_id = body.meta_pixel_id
    if body.linkedin_partner_id is not None:
        settings.linkedin_partner_id = body.linkedin_partner_id
    if body.public_app_url is not None:
        settings.public_app_url = body.public_app_url

    db.add(settings)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="seo.tracking_updated",
        target_type="growth_settings",
        target_id=None,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta=None,
    )
    await db.commit()
    await db.refresh(settings)

    return PlatformGrowthSettingsRead(
        google_analytics_id=settings.google_analytics_id,
        google_tag_manager_id=settings.google_tag_manager_id,
        search_console_verification=settings.search_console_verification,
        meta_pixel_id=settings.meta_pixel_id,
        linkedin_partner_id=settings.linkedin_partner_id,
        robots_txt=settings.robots_txt,
        sitemap_last_generated_at=settings.sitemap_last_generated_at,
        public_app_url=settings.public_app_url,
    )


@platform_seo_router.get("/robots")
async def get_robots_txt(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = await _get_or_create_growth_settings(db)
    await db.commit()
    return {"robots_txt": settings.robots_txt}


@platform_seo_router.patch("/robots")
async def update_robots_txt(
    body: PlatformRobotsUpdate,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = await _get_or_create_growth_settings(db)
    settings.robots_txt = body.robots_txt
    db.add(settings)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="seo.robots_updated",
        target_type="growth_settings",
        target_id=None,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta=None,
    )
    await db.commit()
    return {"robots_txt": settings.robots_txt}


@platform_seo_router.post("/sitemap/regenerate")
async def regenerate_sitemap(
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = await _get_or_create_growth_settings(db)
    now = datetime.now(UTC)
    settings.sitemap_last_generated_at = now
    db.add(settings)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="seo.sitemap_regenerated",
        target_type="growth_settings",
        target_id=None,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"generated_at": now.isoformat()},
    )
    await db.commit()
    return {"message": "Sitemap yeniden oluşturuldu", "generated_at": now.isoformat()}


# ── Growth metrics ────────────────────────────────────────────────────────────


@platform_growth_router.get("/metrics", response_model=PlatformGrowthMetrics)
async def get_growth_metrics(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformGrowthMetrics:
    # Total & active agencies
    total_agencies_result = await db.execute(
        select(func.count()).select_from(Agency).where(Agency.deleted_at.is_(None))
    )
    total_agencies = total_agencies_result.scalar_one()

    active_agencies_result = await db.execute(
        select(func.count())
        .select_from(Agency)
        .where(Agency.deleted_at.is_(None), Agency.status == "active")
    )
    active_agencies = active_agencies_result.scalar_one()

    # Total & active brands
    total_brands_result = await db.execute(
        select(func.count()).select_from(Brand).where(Brand.deleted_at.is_(None))
    )
    total_brands = total_brands_result.scalar_one()

    active_brands_result = await db.execute(
        select(func.count())
        .select_from(Brand)
        .where(Brand.deleted_at.is_(None), Brand.status == "active")
    )
    active_brands = active_brands_result.scalar_one()

    # Total non-platform-admin users
    total_users_result = await db.execute(
        select(func.count())
        .select_from(User)
        .where(
            User.deleted_at.is_(None),
            User.user_type != UserType.PLATFORM_ADMIN.value,
        )
    )
    total_users = total_users_result.scalar_one()

    # New agencies this month
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    new_agencies_result = await db.execute(
        select(func.count())
        .select_from(Agency)
        .where(Agency.deleted_at.is_(None), Agency.created_at >= month_start)
    )
    new_agencies_this_month = new_agencies_result.scalar_one()

    # New users this month
    new_users_result = await db.execute(
        select(func.count())
        .select_from(User)
        .where(
            User.deleted_at.is_(None),
            User.user_type != UserType.PLATFORM_ADMIN.value,
            User.created_at >= month_start,
        )
    )
    new_users_this_month = new_users_result.scalar_one()

    # Agencies with at least one brand
    agencies_with_brand_result = await db.execute(
        select(func.count(func.distinct(Brand.agency_id)))
        .select_from(Brand)
        .where(Brand.deleted_at.is_(None), Brand.agency_id.is_not(None))
    )
    agencies_with_first_brand = agencies_with_brand_result.scalar_one()

    # Agencies with at least one brief
    agencies_with_brief_result = await db.execute(
        select(func.count(func.distinct(Brief.agency_id)))
        .select_from(Brief)
        .where(Brief.deleted_at.is_(None))
    )
    agencies_with_first_brief = agencies_with_brief_result.scalar_one()

    return PlatformGrowthMetrics(
        total_agencies=total_agencies,
        active_agencies=active_agencies,
        total_brands=total_brands,
        active_brands=active_brands,
        total_users=total_users,
        new_agencies_this_month=new_agencies_this_month,
        new_users_this_month=new_users_this_month,
        agencies_with_first_brand=agencies_with_first_brand,
        agencies_with_first_brief=agencies_with_first_brief,
    )

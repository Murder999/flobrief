"""Public, unauthenticated SEO endpoints consumed by the frontend's
app/robots.ts, app/sitemap.ts, and generateMetadata() — so admin-edited
SEO settings actually take effect on the real public pages, not just
in the platform admin screen."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.seo_registry import PUBLIC_PAGE_ROUTES
from app.db.session import get_db
from app.models.platform_seo_settings import PlatformGrowthSettings, PlatformSeoPageSettings

public_seo_router = APIRouter(prefix="/public/seo", tags=["public-seo"])


@public_seo_router.get("/robots")
async def get_public_robots(db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(PlatformGrowthSettings).where(
            PlatformGrowthSettings.setting_key == "default",
            PlatformGrowthSettings.deleted_at.is_(None),
        )
    )
    settings_row = result.scalar_one_or_none()
    return {
        "robots_txt": settings_row.robots_txt if settings_row else None,
        "public_app_url": settings_row.public_app_url if settings_row else None,
    }


@public_seo_router.get("/sitemap-pages")
async def get_public_sitemap_pages(db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(
        select(PlatformSeoPageSettings).where(PlatformSeoPageSettings.deleted_at.is_(None))
    )
    pages_by_key = {p.page_key: p for p in result.scalars().all()}

    out: list[dict] = []
    for route in PUBLIC_PAGE_ROUTES:
        page = pages_by_key.get(route.page_key)
        # Default to indexable=True (matches the model default) when no row
        # exists yet; explicit noindex must be respected and excluded.
        if page is not None and not page.indexable:
            continue
        out.append(
            {
                "path": route.path,
                "updated_at": page.updated_at.isoformat() if page else None,
            }
        )
    return out


@public_seo_router.get("/pages/{page_key}")
async def get_public_page_seo(page_key: str, db: AsyncSession = Depends(get_db)) -> dict:
    if not any(route.page_key == page_key for route in PUBLIC_PAGE_ROUTES):
        raise HTTPException(status_code=404, detail="Unknown public page")

    result = await db.execute(
        select(PlatformSeoPageSettings).where(
            PlatformSeoPageSettings.page_key == page_key,
            PlatformSeoPageSettings.deleted_at.is_(None),
        )
    )
    page = result.scalar_one_or_none()
    if page is None:
        return {
            "title": None,
            "description": None,
            "canonical_url": None,
            "og_title": None,
            "og_description": None,
            "og_image_url": None,
            "indexable": True,
            "follow_links": True,
        }
    return {
        "title": page.title,
        "description": page.description,
        "canonical_url": page.canonical_url,
        "og_title": page.og_title,
        "og_description": page.og_description,
        "og_image_url": page.og_image_url,
        "indexable": page.indexable,
        "follow_links": page.follow_links,
    }

"""Platform admin — global white-label defaults."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_platform_admin_user
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.models.user import User
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.schemas.platform_branding import (
    PlatformBrandingDefaultsRead,
    PlatformBrandingDefaultsUpdate,
)
from app.services.platform_branding_service import PlatformBrandingService

platform_branding_router = APIRouter(prefix="/branding", tags=["platform-branding"])


@platform_branding_router.get("", response_model=PlatformBrandingDefaultsRead)
async def get_platform_branding(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformBrandingDefaultsRead:
    return await PlatformBrandingService(db).get_defaults()


@platform_branding_router.patch("", response_model=PlatformBrandingDefaultsRead)
async def update_platform_branding(
    body: PlatformBrandingDefaultsUpdate,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformBrandingDefaultsRead:
    updated = await PlatformBrandingService(db).update_defaults(body)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="platform_branding.updated",
        target_type="platform_branding_defaults",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"changed_fields": list(body.model_dump(exclude_unset=True).keys())},
    )
    await db.commit()
    return updated


@platform_branding_router.post(
    "/assets", response_model=PlatformBrandingDefaultsRead, status_code=201
)
async def upload_platform_branding_asset(
    asset_type: str,
    request: Request,
    file: UploadFile = File(...),
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformBrandingDefaultsRead:
    if asset_type not in {"logo", "logo_dark", "favicon"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="asset_type must be one of: logo, logo_dark, favicon",
        )
    updated = await PlatformBrandingService(db).upload_asset(file, asset_type)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="platform_branding.asset_uploaded",
        target_type="platform_branding_defaults",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={
            "asset_type": asset_type,
            "filename": file.filename,
            "content_type": file.content_type,
        },
    )
    await db.commit()
    return updated


@platform_branding_router.post("/reset", response_model=PlatformBrandingDefaultsRead)
async def reset_platform_branding(
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformBrandingDefaultsRead:
    reset = await PlatformBrandingService(db).reset_defaults()

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="platform_branding.reset",
        target_type="platform_branding_defaults",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return reset

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.core.rbac import Permission
from app.db.session import get_db
from app.schemas.branding import (
    BrandingSettingsRead,
    BrandingSettingsUpdate,
    CustomDomainCreate,
    CustomDomainCreated,
    CustomDomainRead,
    PublicBrandingView,
)
from app.schemas.platform_branding import PlatformBrandingDefaultsRead
from app.services.branding_service import BrandingService
from app.services.platform_branding_service import PlatformBrandingService
from app.services.storage_service import get_storage_backend

branding_router = APIRouter(prefix="/branding", tags=["branding"])
public_branding_router = APIRouter(prefix="/public/branding", tags=["public-branding"])


def _svc(
    db: AsyncSession = Depends(get_db),
    workspace: WorkspaceContext = Depends(get_workspace_context),
) -> BrandingService:
    return BrandingService(db)


def _require_wl_manage(
    workspace: WorkspaceContext = Depends(get_workspace_context),
) -> WorkspaceContext:
    if not workspace.has_permission(Permission.WHITE_LABEL_MANAGE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Required permission: white_label:manage",
        )
    return workspace


def _svc_manage(
    db: AsyncSession = Depends(get_db),
    workspace: WorkspaceContext = Depends(_require_wl_manage),
) -> BrandingService:
    return BrandingService(db)


# ── Authenticated branding endpoints ──────────────────────────────────────────


@branding_router.get("", response_model=BrandingSettingsRead)
async def get_branding(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> BrandingSettingsRead:
    return await BrandingService(db).get_settings(workspace.agency.id)


@branding_router.patch("", response_model=BrandingSettingsRead)
async def update_branding(
    body: BrandingSettingsUpdate,
    workspace: WorkspaceContext = Depends(_require_wl_manage),
    db: AsyncSession = Depends(get_db),
) -> BrandingSettingsRead:
    return await BrandingService(db).update_settings(workspace.agency.id, body)


@branding_router.post("/assets", response_model=BrandingSettingsRead, status_code=201)
async def upload_branding_asset(
    asset_type: str,
    file: UploadFile = File(...),
    workspace: WorkspaceContext = Depends(_require_wl_manage),
    db: AsyncSession = Depends(get_db),
) -> BrandingSettingsRead:
    _valid_types = {"logo", "email_logo", "favicon", "social_preview"}
    if asset_type not in _valid_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"asset_type must be one of: {', '.join(sorted(_valid_types))}",
        )
    return await BrandingService(db).upload_branding_asset(
        workspace.agency.id, workspace.user.id, file, asset_type
    )


@branding_router.post("/reset", response_model=BrandingSettingsRead)
async def reset_branding(
    workspace: WorkspaceContext = Depends(_require_wl_manage),
    db: AsyncSession = Depends(get_db),
) -> BrandingSettingsRead:
    return await BrandingService(db).reset_settings(workspace.agency.id)


@branding_router.get("/domain", response_model=CustomDomainRead)
async def get_custom_domain(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> CustomDomainRead:
    return await BrandingService(db).get_custom_domain(workspace.agency.id)


@branding_router.post("/domain", response_model=CustomDomainCreated, status_code=201)
async def create_custom_domain(
    body: CustomDomainCreate,
    workspace: WorkspaceContext = Depends(_require_wl_manage),
    db: AsyncSession = Depends(get_db),
) -> CustomDomainCreated:
    return await BrandingService(db).create_custom_domain(workspace.agency.id, body.domain)


# ── Public branding endpoints (no auth) ──────────────────────────────────────


@public_branding_router.get(
    "/by-approval-token/{token}",
    response_model=PublicBrandingView,
)
async def public_branding_by_approval_token(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicBrandingView:
    return await BrandingService(db).get_public_branding_by_approval_token(token)


@public_branding_router.get(
    "/by-report-token/{token}",
    response_model=PublicBrandingView,
)
async def public_branding_by_report_token(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicBrandingView:
    return await BrandingService(db).get_public_branding_by_report_token(token)


@public_branding_router.get("/assets/{asset_id}")
async def serve_branding_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    svc = BrandingService(db)
    asset = await svc.get_public_asset(asset_id)
    storage = get_storage_backend()
    path = storage.get_path(asset.storage_key)
    return FileResponse(
        path=path,
        filename=asset.filename,
        media_type=asset.mime_type,
    )


# ── Platform-level defaults (public, unauthenticated) ─────────────────────────
# Used by the login screen and by agency portals that haven't configured their
# own white-label branding, so a consistent identity always renders.


@public_branding_router.get("/platform-defaults", response_model=PlatformBrandingDefaultsRead)
async def public_platform_branding_defaults(
    db: AsyncSession = Depends(get_db),
) -> PlatformBrandingDefaultsRead:
    return await PlatformBrandingService(db).get_defaults()


@public_branding_router.get("/platform-logo")
async def public_platform_logo(db: AsyncSession = Depends(get_db)) -> FileResponse:
    path, mime_type = await PlatformBrandingService(db).get_asset_file("logo")
    return FileResponse(path=path, media_type=mime_type)


@public_branding_router.get("/platform-logo-dark")
async def public_platform_logo_dark(db: AsyncSession = Depends(get_db)) -> FileResponse:
    path, mime_type = await PlatformBrandingService(db).get_asset_file("logo_dark")
    return FileResponse(path=path, media_type=mime_type)


@public_branding_router.get("/platform-favicon")
async def public_platform_favicon(db: AsyncSession = Depends(get_db)) -> FileResponse:
    path, mime_type = await PlatformBrandingService(db).get_asset_file("favicon")
    return FileResponse(path=path, media_type=mime_type)

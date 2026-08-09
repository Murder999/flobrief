from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context, require_verified
from app.core.rbac import Permission
from app.db.session import get_db
from app.models.agency_member import AgencyMember
from app.models.asset import Asset
from app.models.brand_member import BrandMember
from app.models.user import User
from app.schemas.asset import AssetLinkRead, AssetRead, AssetVersionRead
from app.services.asset_service import AssetService
from app.services.storage_service import get_storage_backend

asset_router = APIRouter(tags=["assets"])


def _svc(
    db: AsyncSession = Depends(get_db),
    workspace: WorkspaceContext = Depends(get_workspace_context),
) -> AssetService:
    return AssetService(db, workspace)


def _require_update_perm(
    workspace: WorkspaceContext = Depends(get_workspace_context),
) -> WorkspaceContext:
    if not workspace.has_permission(Permission.BRIEF_UPDATE):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Gerekli yetki: brief:update")
    return workspace


def _svc_write(
    db: AsyncSession = Depends(get_db),
    workspace: WorkspaceContext = Depends(_require_update_perm),
) -> AssetService:
    return AssetService(db, workspace)


# ── Upload ────────────────────────────────────────────────────────────────────


@asset_router.post(
    "/briefs/{brief_id}/assets",
    response_model=AssetRead,
    status_code=201,
)
async def upload_asset(
    brief_id: uuid.UUID,
    file: UploadFile = File(...),
    svc: AssetService = Depends(_svc_write),
) -> AssetRead:
    return await svc.upload(brief_id, file)


# ── List ──────────────────────────────────────────────────────────────────────


@asset_router.get(
    "/briefs/{brief_id}/assets",
    response_model=list[AssetRead],
)
async def list_assets(
    brief_id: uuid.UUID,
    svc: AssetService = Depends(_svc),
) -> list[AssetRead]:
    return await svc.list_for_brief(brief_id)


# ── Get / Download / Delete ───────────────────────────────────────────────────


@asset_router.get("/assets/{asset_id}", response_model=AssetRead)
async def get_asset(
    asset_id: uuid.UUID,
    svc: AssetService = Depends(_svc),
) -> AssetRead:
    return await svc.get(asset_id)


@asset_router.get("/assets/{asset_id}/download")
async def download_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download an asset file. Requires JWT only — no X-Agency-ID header needed.
    Access is granted if the user is an active member of the asset's agency OR brand."""
    asset = await db.scalar(select(Asset).where(Asset.id == asset_id, Asset.deleted_at.is_(None)))
    if not asset:
        raise HTTPException(status_code=404, detail="Asset bulunamadı")

    # Check: user belongs to the asset's agency or brand
    agency_ok = brand_ok = False
    if asset.agency_id:
        agency_ok = bool(
            await db.scalar(
                select(AgencyMember.id).where(
                    AgencyMember.agency_id == asset.agency_id,
                    AgencyMember.user_id == current_user.id,
                    AgencyMember.status == "active",
                    AgencyMember.deleted_at.is_(None),
                )
            )
        )
    if not agency_ok and asset.brand_id:
        brand_ok = bool(
            await db.scalar(
                select(BrandMember.id).where(
                    BrandMember.brand_id == asset.brand_id,
                    BrandMember.user_id == current_user.id,
                    BrandMember.status == "active",
                    BrandMember.deleted_at.is_(None),
                )
            )
        )

    if not agency_ok and not brand_ok:
        raise HTTPException(status_code=403, detail="Bu dosyaya erişim yetkiniz yok")

    storage = get_storage_backend()
    path = storage.get_path(asset.storage_key)
    return FileResponse(
        path=path,
        filename=asset.original_filename,
        media_type=asset.mime_type,
    )


@asset_router.delete("/assets/{asset_id}")
async def delete_asset(
    asset_id: uuid.UUID,
    svc: AssetService = Depends(_svc_write),
) -> Response:
    await svc.delete(asset_id)
    return Response(status_code=204)


# ── Versions ──────────────────────────────────────────────────────────────────


@asset_router.post(
    "/assets/{asset_id}/versions",
    response_model=AssetVersionRead,
    status_code=201,
)
async def create_asset_version(
    asset_id: uuid.UUID,
    file: UploadFile = File(...),
    svc: AssetService = Depends(_svc_write),
) -> AssetVersionRead:
    return await svc.create_version(asset_id, file)


# ── Links ─────────────────────────────────────────────────────────────────────


@asset_router.post(
    "/briefs/{brief_id}/assets/{asset_id}/link",
    response_model=AssetLinkRead,
    status_code=201,
)
async def link_asset_to_brief(
    brief_id: uuid.UUID,
    asset_id: uuid.UUID,
    svc: AssetService = Depends(_svc_write),
) -> AssetLinkRead:
    return await svc.link_to_brief(asset_id, brief_id)


@asset_router.delete("/assets/{asset_id}/links/{link_id}")
async def unlink_asset(
    asset_id: uuid.UUID,
    link_id: uuid.UUID,
    svc: AssetService = Depends(_svc_write),
) -> Response:
    await svc.unlink(link_id)
    return Response(status_code=204)

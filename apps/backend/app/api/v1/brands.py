from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import (
    WorkspaceContext,
    get_workspace_context,
    require_permission,
)
from app.core.rbac import Permission
from app.db.session import get_db
from app.models.brand import Brand
from app.repositories.user import UserRepository
from app.schemas.brand import BrandMemberRoleUpdate, BrandMemberWithUser, BrandRead, BrandUpdate
from app.services.brand_service import BrandService
from app.services.storage_service import get_storage_backend, normalize_filename

brand_router = APIRouter(prefix="/brands", tags=["brands"])


@brand_router.get("/{brand_id}", response_model=BrandRead)
async def get_brand(
    brand_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> BrandRead:
    svc = BrandService(db)
    brand = await svc.get_brand_for_agency(brand_id, workspace.agency.id, workspace.user)
    return BrandRead.model_validate(brand)


@brand_router.patch("/{brand_id}", response_model=BrandRead)
async def update_brand(
    brand_id: uuid.UUID,
    data: BrandUpdate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.BRAND_UPDATE)),
    db: AsyncSession = Depends(get_db),
) -> BrandRead:
    svc = BrandService(db)
    brand = await svc.update_brand(brand_id, workspace.agency.id, data, workspace.user)
    return BrandRead.model_validate(brand)


@brand_router.get("/{brand_id}/members", response_model=list[BrandMemberWithUser])
async def list_brand_members(
    brand_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[BrandMemberWithUser]:
    svc = BrandService(db)
    members = await svc.list_members(brand_id, workspace.agency.id, workspace.user)
    user_repo = UserRepository(db)
    result = []
    for m in members:
        user = await user_repo.get_by_id(m.user_id)
        result.append(
            BrandMemberWithUser(
                id=m.id,
                brand_id=m.brand_id,
                user_id=m.user_id,
                role=m.role,  # type: ignore[arg-type]
                status=m.status,
                joined_at=m.joined_at,
                created_at=m.created_at,
                user_email=user.email if user else None,
                user_full_name=user.full_name if user else None,
            )
        )
    return result


@brand_router.patch("/{brand_id}/members/{target_user_id}", response_model=BrandMemberWithUser)
async def update_brand_member_role(
    brand_id: uuid.UUID,
    target_user_id: uuid.UUID,
    data: BrandMemberRoleUpdate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.AGENCY_MANAGE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
) -> BrandMemberWithUser:
    svc = BrandService(db)
    member = await svc.update_member_role(
        brand_id, workspace.agency.id, target_user_id, data, workspace.user
    )
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(member.user_id)
    return BrandMemberWithUser(
        id=member.id,
        brand_id=member.brand_id,
        user_id=member.user_id,
        role=member.role,  # type: ignore[arg-type]
        status=member.status,
        joined_at=member.joined_at,
        created_at=member.created_at,
        user_email=user.email if user else None,
        user_full_name=user.full_name if user else None,
    )


_LOGO_ALLOWED = {"image/png", "image/jpeg", "image/webp"}
_LOGO_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


@brand_router.post("/{brand_id}/logo", response_model=BrandRead)
async def upload_brand_logo(
    brand_id: uuid.UUID,
    file: UploadFile = File(...),
    workspace: WorkspaceContext = Depends(require_permission(Permission.BRAND_UPDATE)),
    db: AsyncSession = Depends(get_db),
) -> BrandRead:
    ct = file.content_type or ""
    if ct not in _LOGO_ALLOWED:
        raise HTTPException(
            status_code=422,
            detail="Yalnızca PNG, JPEG veya WebP logo yüklenebilir.",
        )
    data = await file.read()
    if len(data) > _LOGO_MAX_BYTES:
        raise HTTPException(status_code=422, detail="Logo dosyası 5 MB'ı aşamaz.")
    ext = normalize_filename(file.filename or "logo.png").rsplit(".", 1)[-1]
    storage_key = f"brand-logos/{brand_id}/logo.{ext}"
    storage = get_storage_backend()
    await storage.save(data, storage_key)
    logo_url = f"/media/{storage_key}"
    await db.execute(
        update(Brand)
        .where(Brand.id == brand_id, Brand.agency_id == workspace.agency.id)
        .values(logo_url=logo_url)
    )
    await db.commit()
    svc = BrandService(db)
    brand = await svc.get_brand_for_agency(brand_id, workspace.agency.id, workspace.user)
    return BrandRead.model_validate(brand)


@brand_router.delete("/{brand_id}/logo", response_model=BrandRead)
async def delete_brand_logo(
    brand_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.BRAND_UPDATE)),
    db: AsyncSession = Depends(get_db),
) -> BrandRead:
    await db.execute(
        update(Brand)
        .where(Brand.id == brand_id, Brand.agency_id == workspace.agency.id)
        .values(logo_url=None)
    )
    await db.commit()
    svc = BrandService(db)
    brand = await svc.get_brand_for_agency(brand_id, workspace.agency.id, workspace.user)
    return BrandRead.model_validate(brand)


@brand_router.delete("/{brand_id}/members/{target_user_id}", response_model=None)
async def remove_brand_member(
    brand_id: uuid.UUID,
    target_user_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.AGENCY_MANAGE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    svc = BrandService(db)
    await svc.remove_member(brand_id, workspace.agency.id, target_user_id, workspace.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

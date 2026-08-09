from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import (
    WorkspaceContext,
    get_workspace_context,
    require_permission,
    require_verified,
)
from app.core.rbac import Permission
from app.db.session import get_db
from app.models.agency import Agency
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.agency import (
    AgencyCreate,
    AgencyMemberRoleUpdate,
    AgencyMemberWithUser,
    AgencyRead,
    AgencyUpdate,
    AgencyWithRole,
)
from app.schemas.brand import BrandCreate, BrandRead
from app.services.agency_service import AgencyService
from app.services.brand_service import BrandService
from app.services.storage_service import get_storage_backend, normalize_filename

agency_router = APIRouter(prefix="/agencies", tags=["agencies"])

_LOGO_ALLOWED = {"image/png", "image/jpeg", "image/webp"}
_LOGO_MAX_BYTES = 5 * 1024 * 1024


@agency_router.post("", response_model=AgencyRead, status_code=status.HTTP_201_CREATED)
async def create_agency(
    data: AgencyCreate,
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> AgencyRead:
    svc = AgencyService(db)
    agency = await svc.create_agency(data, current_user)
    return AgencyRead.model_validate(agency)


@agency_router.get("/me", response_model=list[AgencyWithRole])
async def list_my_agencies(
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> list[AgencyWithRole]:
    from app.repositories.agency import AgencyRepository
    from app.repositories.agency_member import AgencyMemberRepository

    agency_repo = AgencyRepository(db)
    member_repo = AgencyMemberRepository(db)
    agencies = await agency_repo.list_for_user(current_user.id)

    result = []
    for ag in agencies:
        member = await member_repo.get_membership(ag.id, current_user.id)
        if member:
            result.append(
                AgencyWithRole(
                    id=ag.id,
                    name=ag.name,
                    slug=ag.slug,
                    status=ag.status,  # type: ignore[arg-type]
                    owner_user_id=ag.owner_user_id,
                    plan_id=ag.plan_id,
                    created_at=ag.created_at,
                    updated_at=ag.updated_at,
                    member_role=member.role,
                    member_status=member.status,
                )
            )
    return result


@agency_router.get("/{agency_id}", response_model=AgencyRead)
async def get_agency(
    agency_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
) -> AgencyRead:
    if workspace.agency.id != agency_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Agency ID eşleşmiyor")
    return AgencyRead.model_validate(workspace.agency)


@agency_router.patch("/{agency_id}", response_model=AgencyRead)
async def update_agency(
    agency_id: uuid.UUID,
    data: AgencyUpdate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.AGENCY_UPDATE)),
    db: AsyncSession = Depends(get_db),
) -> AgencyRead:
    if workspace.agency.id != agency_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Agency ID eşleşmiyor")
    svc = AgencyService(db)
    agency = await svc.update_agency(agency_id, data, workspace.user)
    return AgencyRead.model_validate(agency)


@agency_router.get("/{agency_id}/members", response_model=list[AgencyMemberWithUser])
async def list_members(
    agency_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[AgencyMemberWithUser]:
    if workspace.agency.id != agency_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Agency ID eşleşmiyor")
    svc = AgencyService(db)
    members = await svc.list_members(agency_id, workspace.user)
    user_repo = UserRepository(db)
    result = []
    for m in members:
        user = await user_repo.get_by_id(m.user_id)
        result.append(
            AgencyMemberWithUser(
                id=m.id,
                agency_id=m.agency_id,
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


@agency_router.patch(
    "/{agency_id}/members/{target_user_id}",
    response_model=AgencyMemberWithUser,
)
async def update_member_role(
    agency_id: uuid.UUID,
    target_user_id: uuid.UUID,
    data: AgencyMemberRoleUpdate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.AGENCY_MANAGE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
) -> AgencyMemberWithUser:
    if workspace.agency.id != agency_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Agency ID eşleşmiyor")
    svc = AgencyService(db)
    member = await svc.update_member_role(agency_id, target_user_id, data, workspace.user)
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(member.user_id)
    return AgencyMemberWithUser(
        id=member.id,
        agency_id=member.agency_id,
        user_id=member.user_id,
        role=member.role,  # type: ignore[arg-type]
        status=member.status,
        joined_at=member.joined_at,
        created_at=member.created_at,
        user_email=user.email if user else None,
        user_full_name=user.full_name if user else None,
    )


@agency_router.delete("/{agency_id}/members/{target_user_id}", response_model=None)
async def remove_member(
    agency_id: uuid.UUID,
    target_user_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.AGENCY_MANAGE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if workspace.agency.id != agency_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Agency ID eşleşmiyor")
    svc = AgencyService(db)
    await svc.remove_member(agency_id, target_user_id, workspace.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Agency logo ───────────────────────────────────────────────────────────────


@agency_router.post("/{agency_id}/logo", response_model=AgencyRead)
async def upload_agency_logo(
    agency_id: uuid.UUID,
    file: UploadFile = File(...),
    workspace: WorkspaceContext = Depends(require_permission(Permission.AGENCY_UPDATE)),
    db: AsyncSession = Depends(get_db),
) -> AgencyRead:
    if workspace.agency.id != agency_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Agency ID eşleşmiyor")
    ct = file.content_type or ""
    if ct not in _LOGO_ALLOWED:
        raise HTTPException(
            status_code=422,
            detail="Yalnızca PNG, JPEG veya WebP yüklenebilir.",
        )
    data = await file.read()
    if len(data) > _LOGO_MAX_BYTES:
        raise HTTPException(status_code=422, detail="Logo 5 MB'ı aşamaz.")
    ext = normalize_filename(file.filename or "logo.png").rsplit(".", 1)[-1]
    storage_key = f"agency-logos/{agency_id}/logo.{ext}"
    await get_storage_backend().save(data, storage_key)
    logo_url = f"/media/{storage_key}"
    await db.execute(update(Agency).where(Agency.id == agency_id).values(logo_url=logo_url))
    await db.commit()
    await db.refresh(workspace.agency)
    return AgencyRead.model_validate(workspace.agency)


@agency_router.delete("/{agency_id}/logo", response_model=AgencyRead)
async def delete_agency_logo(
    agency_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.AGENCY_UPDATE)),
    db: AsyncSession = Depends(get_db),
) -> AgencyRead:
    if workspace.agency.id != agency_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Agency ID eşleşmiyor")
    await db.execute(update(Agency).where(Agency.id == agency_id).values(logo_url=None))
    await db.commit()
    await db.refresh(workspace.agency)
    return AgencyRead.model_validate(workspace.agency)


# ── Brands under agency ───────────────────────────────────────────────────────


@agency_router.get("/{agency_id}/brands", response_model=list[BrandRead])
async def list_brands(
    agency_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[BrandRead]:
    if workspace.agency.id != agency_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Agency ID eşleşmiyor")
    svc = BrandService(db)
    brands = await svc.list_brands_for_agency(agency_id, workspace.user)
    return [BrandRead.model_validate(b) for b in brands]


@agency_router.post(
    "/{agency_id}/brands",
    response_model=BrandRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_brand(
    agency_id: uuid.UUID,
    data: BrandCreate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.BRAND_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> BrandRead:
    if workspace.agency.id != agency_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Agency ID eşleşmiyor")
    svc = BrandService(db)
    brand = await svc.create_brand(agency_id, data, workspace.user)
    return BrandRead.model_validate(brand)

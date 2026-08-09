"""Brand Identity / Marka DNA endpoints (agency-scoped)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.db.session import get_db
from app.schemas.brand_identity import (
    BrandDNASummary,
    BrandIdentityDocumentRead,
    BrandIdentityOverview,
    BrandIdentityProfileRead,
    BrandIdentityProfileUpdate,
    BrandIdentityRevisionRead,
)
from app.services.brand_identity_service import BrandIdentityService

brand_identity_router = APIRouter(prefix="/brands", tags=["brand-identity"])


def _svc(db: AsyncSession = Depends(get_db)) -> BrandIdentityService:
    return BrandIdentityService(db)


@brand_identity_router.get(
    "/{brand_id}/identity",
    response_model=BrandIdentityOverview,
)
async def get_brand_identity_overview(
    brand_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    svc: BrandIdentityService = Depends(_svc),
) -> BrandIdentityOverview:
    return await svc.get_overview(brand_id, workspace.agency.id)


@brand_identity_router.post(
    "/{brand_id}/identity/documents",
    response_model=BrandIdentityDocumentRead,
    status_code=201,
)
async def upload_identity_document(
    brand_id: uuid.UUID,
    file: UploadFile = File(...),
    workspace: WorkspaceContext = Depends(get_workspace_context),
    svc: BrandIdentityService = Depends(_svc),
) -> BrandIdentityDocumentRead:
    return await svc.upload_document(brand_id, workspace.agency.id, file, workspace.user)


@brand_identity_router.get(
    "/{brand_id}/identity/documents",
    response_model=list[BrandIdentityDocumentRead],
)
async def list_identity_documents(
    brand_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    svc: BrandIdentityService = Depends(_svc),
) -> list[BrandIdentityDocumentRead]:
    return await svc.list_documents(brand_id, workspace.agency.id)


@brand_identity_router.post(
    "/{brand_id}/identity/documents/{document_id}/analyze",
    response_model=BrandIdentityDocumentRead,
)
async def analyze_identity_document(
    brand_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    svc: BrandIdentityService = Depends(_svc),
) -> BrandIdentityDocumentRead:
    return await svc.analyze_document(brand_id, document_id, workspace.agency.id, workspace.user)


@brand_identity_router.patch(
    "/{brand_id}/identity/profile",
    response_model=BrandIdentityProfileRead,
)
async def update_identity_profile(
    brand_id: uuid.UUID,
    data: BrandIdentityProfileUpdate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    svc: BrandIdentityService = Depends(_svc),
) -> BrandIdentityProfileRead:
    return await svc.update_profile(brand_id, workspace.agency.id, data, workspace.user)


@brand_identity_router.post(
    "/{brand_id}/identity/profile/approve",
    response_model=BrandIdentityProfileRead,
)
async def approve_identity_profile(
    brand_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    svc: BrandIdentityService = Depends(_svc),
) -> BrandIdentityProfileRead:
    return await svc.approve_profile(brand_id, workspace.agency.id, workspace.user)


@brand_identity_router.get(
    "/{brand_id}/identity/revisions",
    response_model=list[BrandIdentityRevisionRead],
)
async def list_identity_revisions(
    brand_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    svc: BrandIdentityService = Depends(_svc),
) -> list[BrandIdentityRevisionRead]:
    return await svc.list_revisions(brand_id, workspace.agency.id)


@brand_identity_router.get(
    "/{brand_id}/identity/dna-summary",
    response_model=BrandDNASummary,
)
async def get_brand_dna_summary(
    brand_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    svc: BrandIdentityService = Depends(_svc),
) -> BrandDNASummary:
    # Verify brand belongs to agency
    await svc._require_brand(brand_id, workspace.agency.id)
    return await svc.get_dna_summary(brand_id)

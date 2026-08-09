from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.db.session import get_db
from app.schemas.approval import (
    AddPublicCommentRequest,
    ApprovalCommentRead,
    ApprovalRead,
    BriefVersionRead,
    BriefVersionSummary,
    PublicApprovalView,
    PublicApproveRequest,
    PublicRevisionRequest,
    SendToApprovalResponse,
)
from app.services.approval_service import ApprovalService, PublicApprovalService

# Private: requires agency workspace context
approval_router = APIRouter(tags=["approvals"])

# Public: no auth required
public_approval_router = APIRouter(prefix="/public/approvals", tags=["approvals-public"])


def _svc(
    db: AsyncSession = Depends(get_db),
    workspace: WorkspaceContext = Depends(get_workspace_context),
) -> ApprovalService:
    return ApprovalService(db, workspace)


def _pub_svc(db: AsyncSession = Depends(get_db)) -> PublicApprovalService:
    return PublicApprovalService(db)


# ── Private routes ────────────────────────────────────────────────────────────


@approval_router.post(
    "/briefs/{brief_id}/send-approval",
    response_model=SendToApprovalResponse,
    status_code=201,
)
async def send_to_approval(
    brief_id: uuid.UUID,
    svc: ApprovalService = Depends(_svc),
) -> SendToApprovalResponse:
    return await svc.send_to_approval(brief_id)


@approval_router.get("/briefs/{brief_id}/approvals", response_model=list[ApprovalRead])
async def list_approvals(
    brief_id: uuid.UUID,
    svc: ApprovalService = Depends(_svc),
) -> list[ApprovalRead]:
    return await svc.list_approvals(brief_id)


@approval_router.delete("/briefs/{brief_id}/approvals/{approval_id}", response_model=ApprovalRead)
async def revoke_approval(
    brief_id: uuid.UUID,
    approval_id: uuid.UUID,
    svc: ApprovalService = Depends(_svc),
) -> ApprovalRead:
    return await svc.revoke_approval(brief_id, approval_id)


@approval_router.get("/briefs/{brief_id}/versions", response_model=list[BriefVersionSummary])
async def list_versions(
    brief_id: uuid.UUID,
    svc: ApprovalService = Depends(_svc),
) -> list[BriefVersionSummary]:
    return await svc.list_versions(brief_id)


@approval_router.get("/briefs/{brief_id}/versions/{version_id}", response_model=BriefVersionRead)
async def get_version(
    brief_id: uuid.UUID,
    version_id: uuid.UUID,
    svc: ApprovalService = Depends(_svc),
) -> BriefVersionRead:
    return await svc.get_version(brief_id, version_id)


@approval_router.get(
    "/briefs/{brief_id}/approvals/{approval_id}/comments",
    response_model=list[ApprovalCommentRead],
)
async def list_comments(
    brief_id: uuid.UUID,
    approval_id: uuid.UUID,
    svc: ApprovalService = Depends(_svc),
) -> list[ApprovalCommentRead]:
    return await svc.list_comments(brief_id, approval_id)


# ── Public routes ─────────────────────────────────────────────────────────────


@public_approval_router.get("/{token}", response_model=PublicApprovalView)
async def get_approval_by_token(
    token: str,
    svc: PublicApprovalService = Depends(_pub_svc),
) -> PublicApprovalView:
    return await svc.get_by_token(token)


@public_approval_router.post("/{token}/approve", response_model=dict)
async def approve_by_token(
    token: str,
    payload: PublicApproveRequest,
    svc: PublicApprovalService = Depends(_pub_svc),
) -> dict:
    return await svc.approve(token, payload)


@public_approval_router.post("/{token}/revision", response_model=dict)
async def request_revision_by_token(
    token: str,
    payload: PublicRevisionRequest,
    svc: PublicApprovalService = Depends(_pub_svc),
) -> dict:
    return await svc.request_revision(token, payload)


@public_approval_router.post(
    "/{token}/comment",
    response_model=ApprovalCommentRead,
    status_code=201,
)
async def add_public_comment(
    token: str,
    payload: AddPublicCommentRequest,
    svc: PublicApprovalService = Depends(_pub_svc),
) -> ApprovalCommentRead:
    return await svc.add_comment(token, payload)

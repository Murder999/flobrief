from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.core.rbac import Permission
from app.db.session import get_db
from app.models.asset import Asset, AssetLink
from app.schemas.asset import AssetRead
from app.schemas.comment import (
    AddCommentRequest,
    CommentRead,
    ThreadCreate,
    ThreadRead,
    UpdateCommentRequest,
)
from app.services.comment_service import CommentService
from app.services.storage_service import (
    get_storage_backend,
    normalize_filename,
    validate_file_size,
    validate_mime_type,
)

comment_router = APIRouter(tags=["comments"])


def _svc(
    db: AsyncSession = Depends(get_db),
    workspace: WorkspaceContext = Depends(get_workspace_context),
) -> CommentService:
    return CommentService(db, workspace)


def _require_comment_perm(
    workspace: WorkspaceContext = Depends(get_workspace_context),
) -> WorkspaceContext:
    if not workspace.has_permission(Permission.BRIEF_COMMENT):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Gerekli yetki: brief:comment")
    return workspace


def _svc_with_perm(
    db: AsyncSession = Depends(get_db),
    workspace: WorkspaceContext = Depends(_require_comment_perm),
) -> CommentService:
    return CommentService(db, workspace)


# ── Thread endpoints ──────────────────────────────────────────────────────────


@comment_router.post(
    "/briefs/{brief_id}/threads",
    response_model=ThreadRead,
    status_code=201,
)
async def create_thread(
    brief_id: uuid.UUID,
    payload: ThreadCreate,
    svc: CommentService = Depends(_svc_with_perm),
) -> ThreadRead:
    return await svc.create_thread(brief_id, payload)


@comment_router.get(
    "/briefs/{brief_id}/threads",
    response_model=list[ThreadRead],
)
async def list_threads(
    brief_id: uuid.UUID,
    svc: CommentService = Depends(_svc),
) -> list[ThreadRead]:
    return await svc.list_threads(brief_id)


@comment_router.post(
    "/threads/{thread_id}/resolve",
    response_model=ThreadRead,
)
async def resolve_thread(
    thread_id: uuid.UUID,
    svc: CommentService = Depends(_svc_with_perm),
) -> ThreadRead:
    return await svc.resolve_thread(thread_id)


@comment_router.post(
    "/threads/{thread_id}/reopen",
    response_model=ThreadRead,
)
async def reopen_thread(
    thread_id: uuid.UUID,
    svc: CommentService = Depends(_svc_with_perm),
) -> ThreadRead:
    return await svc.reopen_thread(thread_id)


# ── Comment endpoints ─────────────────────────────────────────────────────────


@comment_router.post(
    "/threads/{thread_id}/comments",
    response_model=CommentRead,
    status_code=201,
)
async def add_comment(
    thread_id: uuid.UUID,
    payload: AddCommentRequest,
    svc: CommentService = Depends(_svc_with_perm),
) -> CommentRead:
    return await svc.add_comment(thread_id, payload)


@comment_router.patch(
    "/threads/{thread_id}/comments/{comment_id}",
    response_model=CommentRead,
)
async def update_comment(
    thread_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: UpdateCommentRequest,
    svc: CommentService = Depends(_svc_with_perm),
) -> CommentRead:
    return await svc.update_comment(thread_id, comment_id, payload)


@comment_router.delete("/threads/{thread_id}/comments/{comment_id}")
async def delete_comment(
    thread_id: uuid.UUID,
    comment_id: uuid.UUID,
    svc: CommentService = Depends(_svc_with_perm),
) -> Response:
    await svc.delete_comment(thread_id, comment_id)
    return Response(status_code=204)


# ── Comment attachment pre-upload ─────────────────────────────────────────────


@comment_router.post(
    "/briefs/{brief_id}/comment-attachments",
    response_model=AssetRead,
    status_code=201,
    tags=["comments"],
)
async def upload_comment_attachment(
    brief_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    workspace: WorkspaceContext = Depends(get_workspace_context),
) -> AssetRead:
    """Upload a file to be attached to a comment. Returns an asset that can
    be referenced by asset ID when creating or replying to a thread."""
    data = await file.read()
    mime = file.content_type or "application/octet-stream"
    validate_mime_type(mime)
    validate_file_size(len(data))

    original_name = file.filename or "attachment"
    safe_name = normalize_filename(original_name)
    storage_key = f"{workspace.agency.id}/comments/{safe_name}"

    storage = get_storage_backend()
    await storage.save(data, storage_key)

    asset = Asset(
        agency_id=workspace.agency.id,
        uploaded_by_id=workspace.user.id,
        filename=safe_name,
        original_filename=original_name[:500],
        mime_type=mime,
        size_bytes=len(data),
        storage_provider="local",
        storage_key=storage_key,
        checksum=hashlib.sha256(data).hexdigest(),
        visibility="internal",
    )
    db.add(asset)
    await db.flush()

    # Pre-link to brief so download auth check succeeds
    db.add(AssetLink(asset_id=asset.id, brief_id=brief_id))
    await db.commit()
    await db.refresh(asset)
    return AssetRead.model_validate(asset)

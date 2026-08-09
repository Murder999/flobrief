"""Deliverable endpoints — agency creates/manages production outputs for briefs."""

from __future__ import annotations

import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import (
    WorkspaceContext,
    get_workspace_context,
    require_permission,
)
from app.core.html_sanitizer import sanitize_html
from app.core.rbac import Permission
from app.db.session import get_db
from app.models.asset import Asset, AssetLink
from app.models.brief import Brief
from app.models.deliverable import Deliverable
from app.models.deliverable_annotation import AnnotationReply, DeliverableAnnotation
from app.models.enums import NotificationEventType
from app.models.user import User
from app.schemas.asset import AssetRead
from app.schemas.deliverable import DeliverableCreate, DeliverableRead, DeliverableUpdate
from app.schemas.deliverable_annotation import (
    AnnotationCreate,
    AnnotationRead,
    AnnotationReplyCreate,
    AnnotationReplyRead,
)
from app.services.deliverable_versioning import (
    compute_latest_version_ids,
    get_latest_version_ids_for_brief,
)
from app.services.media_metadata import extract_image_dimensions
from app.services.mention_service import MentionService
from app.services.storage_service import (
    get_storage_backend,
    normalize_filename,
    validate_file_size,
    validate_mime_type,
)

deliverable_router = APIRouter(tags=["deliverables"])
logger = logging.getLogger(__name__)

UTC_NOW = __import__("datetime").datetime.now(__import__("datetime").UTC)


def _utcnow() -> __import__("datetime").datetime:
    from datetime import UTC, datetime

    return datetime.now(UTC)


async def _require_brief(
    brief_id: uuid.UUID,
    workspace: WorkspaceContext,
    db: AsyncSession,
) -> Brief:
    result = await db.execute(
        select(Brief).where(
            Brief.id == brief_id,
            Brief.agency_id == workspace.agency.id,
            Brief.deleted_at.is_(None),
        )
    )
    brief = result.scalar_one_or_none()
    if not brief:
        raise HTTPException(status_code=404, detail="Brief bulunamadı")
    return brief


async def _require_deliverable(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    workspace: WorkspaceContext,
    db: AsyncSession,
) -> Deliverable:
    result = await db.execute(
        select(Deliverable).where(
            Deliverable.id == deliverable_id,
            Deliverable.brief_id == brief_id,
            Deliverable.agency_id == workspace.agency.id,
            Deliverable.deleted_at.is_(None),
        )
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Deliverable bulunamadı")
    return d


async def _load_assets_for_deliverable(
    deliverable_id: uuid.UUID,
    db: AsyncSession,
) -> list[AssetRead]:
    rows = await db.execute(
        select(Asset)
        .join(
            AssetLink,
            and_(
                AssetLink.asset_id == Asset.id,
                AssetLink.deliverable_id == deliverable_id,
                Asset.deleted_at.is_(None),
            ),
        )
        .order_by(Asset.created_at.asc())
    )
    return [AssetRead.model_validate(a) for a in rows.scalars().all()]


async def _deliverable_to_read(
    d: Deliverable,
    db: AsyncSession,
    latest_ids: set[uuid.UUID] | None = None,
) -> DeliverableRead:
    assets = await _load_assets_for_deliverable(d.id, db)
    if latest_ids is None:
        latest_ids = await get_latest_version_ids_for_brief(db, d.brief_id)
    return DeliverableRead(
        id=d.id,
        agency_id=d.agency_id,
        brand_id=d.brand_id,
        brief_id=d.brief_id,
        title=d.title,
        description=d.description,
        description_html=d.description_html,
        deliverable_type=d.deliverable_type,
        status=d.status,
        version_number=d.version_number,
        revision_count=d.revision_count,
        revision_note=d.revision_note,
        approve_note=d.approve_note,
        is_latest_version=d.id in latest_ids,
        submitted_by_id=d.submitted_by_id,
        submitted_at=d.submitted_at,
        approved_by_id=d.approved_by_id,
        approved_at=d.approved_at,
        created_at=d.created_at,
        updated_at=d.updated_at,
        assets=assets,
    )


# ── Agency deliverable endpoints ───────────────────────────────────────────────


@deliverable_router.post(
    "/briefs/{brief_id}/deliverables",
    response_model=DeliverableRead,
    status_code=201,
)
async def create_deliverable(
    brief_id: uuid.UUID,
    data: DeliverableCreate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.BRIEF_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> DeliverableRead:
    brief = await _require_brief(brief_id, workspace, db)
    d = Deliverable(
        agency_id=workspace.agency.id,
        brand_id=brief.brand_id,
        brief_id=brief_id,
        title=data.title,
        description=data.description,
        description_html=data.description_html,
        deliverable_type=data.deliverable_type,
        status="draft",
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return await _deliverable_to_read(d, db)


@deliverable_router.get(
    "/briefs/{brief_id}/deliverables",
    response_model=list[DeliverableRead],
)
async def list_deliverables(
    brief_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[DeliverableRead]:
    await _require_brief(brief_id, workspace, db)
    rows = await db.execute(
        select(Deliverable)
        .where(
            Deliverable.brief_id == brief_id,
            Deliverable.agency_id == workspace.agency.id,
            Deliverable.deleted_at.is_(None),
        )
        .order_by(Deliverable.created_at.asc())
    )
    deliverables = rows.scalars().all()
    latest_ids = compute_latest_version_ids(deliverables)
    return [await _deliverable_to_read(d, db, latest_ids) for d in deliverables]


@deliverable_router.get(
    "/briefs/{brief_id}/deliverables/{deliverable_id}",
    response_model=DeliverableRead,
)
async def get_deliverable(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> DeliverableRead:
    d = await _require_deliverable(brief_id, deliverable_id, workspace, db)
    return await _deliverable_to_read(d, db)


@deliverable_router.patch(
    "/briefs/{brief_id}/deliverables/{deliverable_id}",
    response_model=DeliverableRead,
)
async def update_deliverable(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    data: DeliverableUpdate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> DeliverableRead:
    d = await _require_deliverable(brief_id, deliverable_id, workspace, db)
    if d.status not in {"draft", "revision_requested"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yalnızca taslak veya revizyon durumundaki deliverable güncellenebilir",
        )
    if data.title is not None:
        d.title = data.title
    if data.description is not None:
        d.description = data.description
    if data.description_html is not None:
        d.description_html = data.description_html
    if data.deliverable_type is not None:
        d.deliverable_type = data.deliverable_type
    await db.commit()
    await db.refresh(d)
    return await _deliverable_to_read(d, db)


@deliverable_router.delete(
    "/briefs/{brief_id}/deliverables/{deliverable_id}",
    status_code=204,
    response_model=None,
)
async def delete_deliverable(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    d = await _require_deliverable(brief_id, deliverable_id, workspace, db)
    if d.status not in {"draft", "revision_requested", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Onaylanmış veya gönderilmiş deliverable silinemez",
        )
    from datetime import UTC, datetime

    d.deleted_at = datetime.now(UTC)
    await db.commit()


@deliverable_router.post(
    "/briefs/{brief_id}/deliverables/{deliverable_id}/submit",
    response_model=DeliverableRead,
)
async def submit_deliverable(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> DeliverableRead:
    from datetime import UTC, datetime

    from app.services.notification_dispatcher import NotificationDispatcher

    d = await _require_deliverable(brief_id, deliverable_id, workspace, db)
    if d.status not in {"draft", "revision_requested"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yalnızca taslak veya revizyon durumundaki deliverable gönderilebilir",
        )
    brief = await _require_brief(brief_id, workspace, db)
    d.status = "submitted"
    d.submitted_by_id = workspace.user.id
    d.submitted_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(d)

    try:
        dispatcher = NotificationDispatcher(db)
        recipients: list[uuid.UUID] | None = None
        if d.brand_id:
            brand_users = await dispatcher.get_brand_members(d.brand_id)
            recipients = [u.id for u in brand_users]
        await dispatcher.emit(
            NotificationEventType.DELIVERABLE_SUBMITTED.value,
            payload={
                "brief_id": str(brief_id),
                "brief_title": brief.title,
                "deliverable_id": str(d.id),
                "deliverable_title": d.title,
                "agency_name": workspace.agency.name,
                "revision_count": d.revision_count,
                "summary": f"Yeni teslimat incelemenizi bekliyor: {d.title}",
            },
            agency_id=workspace.agency.id,
            brand_id=d.brand_id,
            actor_user_id=workspace.user.id,
            recipient_ids=recipients,
        )
    except Exception:
        pass

    return await _deliverable_to_read(d, db)


@deliverable_router.post(
    "/briefs/{brief_id}/deliverables/{deliverable_id}/assets",
    response_model=AssetRead,
    status_code=201,
)
async def upload_deliverable_asset(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    file: UploadFile = File(...),
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> AssetRead:
    d = await _require_deliverable(brief_id, deliverable_id, workspace, db)
    if d.status not in {"draft", "revision_requested"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yalnızca taslak veya revizyon durumundaki deliverable'a dosya yüklenebilir",
        )

    data = await file.read()
    mime = file.content_type or "application/octet-stream"
    validate_mime_type(mime)
    validate_file_size(len(data))

    checksum = hashlib.sha256(data).hexdigest()
    original_name = file.filename or "upload"
    safe_name = normalize_filename(original_name)
    storage_key = f"{workspace.agency.id}/deliverables/{safe_name}"

    storage = get_storage_backend()
    await storage.save(data, storage_key)

    dimensions = extract_image_dimensions(data, mime)

    asset = Asset(
        agency_id=workspace.agency.id,
        brand_id=d.brand_id,
        uploaded_by_id=workspace.user.id,
        filename=safe_name,
        original_filename=original_name[:500],
        mime_type=mime,
        size_bytes=len(data),
        storage_provider="local",
        storage_key=storage_key,
        checksum=checksum,
        visibility="client_visible",
        width_px=dimensions[0] if dimensions else None,
        height_px=dimensions[1] if dimensions else None,
    )
    db.add(asset)
    await db.flush()

    link = AssetLink(
        asset_id=asset.id,
        brief_id=brief_id,
        deliverable_id=d.id,
    )
    db.add(link)
    await db.commit()
    await db.refresh(asset)
    return AssetRead.model_validate(asset)


# ── Annotation helpers ─────────────────────────────────────────────────────────


async def _require_annotation(
    deliverable_id: uuid.UUID,
    annotation_id: uuid.UUID,
    workspace: WorkspaceContext,
    db: AsyncSession,
) -> DeliverableAnnotation:
    result = await db.execute(
        select(DeliverableAnnotation).where(
            DeliverableAnnotation.id == annotation_id,
            DeliverableAnnotation.deliverable_id == deliverable_id,
            DeliverableAnnotation.agency_id == workspace.agency.id,
            DeliverableAnnotation.deleted_at.is_(None),
        )
    )
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation bulunamadı")
    return ann


async def _annotation_to_read(ann: DeliverableAnnotation, db: AsyncSession) -> AnnotationRead:
    mention_service = MentionService(db)
    rows = await db.execute(
        select(AnnotationReply)
        .where(
            AnnotationReply.annotation_id == ann.id,
            AnnotationReply.deleted_at.is_(None),
        )
        .order_by(AnnotationReply.created_at.asc())
    )
    replies = []
    for r in rows.scalars().all():
        reply_mentions = await mention_service.get_inline_mentions(
            source_type="annotation_reply", source_id=r.id
        )
        replies.append(
            AnnotationReplyRead.model_validate(r).model_copy(update={"mentions": reply_mentions})
        )
    ann_mentions = await mention_service.get_inline_mentions(
        source_type="annotation", source_id=ann.id
    )
    created_by_name: str | None = None
    if ann.created_by_id is not None:
        creator = await db.get(User, ann.created_by_id)
        created_by_name = creator.full_name if creator else None
    return AnnotationRead(
        id=ann.id,
        agency_id=ann.agency_id,
        brand_id=ann.brand_id,
        brief_id=ann.brief_id,
        deliverable_id=ann.deliverable_id,
        asset_id=ann.asset_id,
        version_number=ann.version_number,
        x_percent=ann.x_percent,
        y_percent=ann.y_percent,
        label_number=ann.label_number,
        status=ann.status,
        annotation_type=ann.annotation_type,
        visibility=ann.visibility,
        body=ann.body,
        body_html=ann.body_html,
        created_by_id=ann.created_by_id,
        created_by_name=created_by_name,
        resolved_by_id=ann.resolved_by_id,
        resolved_at=ann.resolved_at,
        created_at=ann.created_at,
        updated_at=ann.updated_at,
        replies=replies,
        mentions=ann_mentions,
    )


# ── Agency annotation endpoints ────────────────────────────────────────────────


@deliverable_router.get(
    "/briefs/{brief_id}/deliverables/{deliverable_id}/annotations",
    response_model=list[AnnotationRead],
)
async def list_annotations(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    version_number: int | None = None,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[AnnotationRead]:
    await _require_deliverable(brief_id, deliverable_id, workspace, db)
    q = select(DeliverableAnnotation).where(
        DeliverableAnnotation.deliverable_id == deliverable_id,
        DeliverableAnnotation.agency_id == workspace.agency.id,
        DeliverableAnnotation.deleted_at.is_(None),
    )
    if version_number is not None:
        q = q.where(DeliverableAnnotation.version_number == version_number)
    q = q.order_by(DeliverableAnnotation.label_number.asc())
    rows = await db.execute(q)
    anns = rows.scalars().all()
    return [await _annotation_to_read(a, db) for a in anns]


@deliverable_router.post(
    "/briefs/{brief_id}/deliverables/{deliverable_id}/annotations",
    response_model=AnnotationRead,
    status_code=201,
)
async def create_annotation(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    data: AnnotationCreate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> AnnotationRead:
    d = await _require_deliverable(brief_id, deliverable_id, workspace, db)

    # Auto-increment label_number within this deliverable + version
    count_result = await db.execute(
        select(func.count())
        .select_from(DeliverableAnnotation)
        .where(
            DeliverableAnnotation.deliverable_id == deliverable_id,
            DeliverableAnnotation.version_number == data.version_number,
            DeliverableAnnotation.deleted_at.is_(None),
        )
    )
    next_label = (count_result.scalar() or 0) + 1

    ann = DeliverableAnnotation(
        agency_id=workspace.agency.id,
        brand_id=d.brand_id,
        brief_id=brief_id,
        deliverable_id=deliverable_id,
        asset_id=data.asset_id,
        version_number=data.version_number,
        x_percent=data.x_percent,
        y_percent=data.y_percent,
        label_number=next_label,
        status="open",
        annotation_type=data.annotation_type,
        visibility=data.visibility,
        body=data.body.strip(),
        body_html=sanitize_html(data.body_html),
        created_by_id=workspace.user.id,
    )
    db.add(ann)
    await db.commit()
    await db.refresh(ann)

    if ann.visibility == "client_visible" and d.brand_id:
        try:
            from app.services.notification_dispatcher import NotificationDispatcher

            brief = await _require_brief(brief_id, workspace, db)
            dispatcher = NotificationDispatcher(db)
            recipients = [u.id for u in await dispatcher.get_brand_members(d.brand_id)]
            await dispatcher.emit(
                NotificationEventType.ANNOTATION_CREATED.value,
                payload={
                    "brief_id": str(brief_id),
                    "brief_title": brief.title,
                    "deliverable_id": str(d.id),
                    "deliverable_title": d.title,
                    "annotation_id": str(ann.id),
                    "label_number": ann.label_number,
                    "agency_name": workspace.agency.name,
                    "summary": (
                        f"{d.title} üzerinde yeni bir revizyon notu eklendi "
                        f"(#{ann.label_number})"
                    ),
                },
                agency_id=workspace.agency.id,
                brand_id=d.brand_id,
                actor_user_id=workspace.user.id,
                recipient_ids=recipients,
            )
        except Exception:
            logger.exception("Failed to dispatch annotation.created notification")

    if data.mentioned_user_ids:
        try:
            brief_for_mentions = await _require_brief(brief_id, workspace, db)
            await MentionService(db).sync_mentions_for_source(
                agency_id=workspace.agency.id,
                brand_id=d.brand_id,
                brief_id=brief_id,
                deliverable_id=d.id,
                source_type="annotation",
                source_id=ann.id,
                actor_user_id=workspace.user.id,
                actor_name=workspace.user.full_name,
                body_text=ann.body or "",
                mentioned_user_ids=data.mentioned_user_ids,
                portal="agency",
                notification_event_type=NotificationEventType.MENTIONED_IN_ANNOTATION.value,
                notification_payload_extra={
                    "brief_id": str(brief_id),
                    "brief_title": brief_for_mentions.title,
                    "deliverable_id": str(d.id),
                    "deliverable_title": d.title,
                    "annotation_id": str(ann.id),
                    "label_number": ann.label_number,
                    "summary": (
                        f"{workspace.user.full_name} sizi {d.title} üzerindeki bir "
                        f"revizyon notunda etiketledi"
                    ),
                },
            )
            await db.commit()
        except Exception:
            logger.exception("Failed to dispatch annotation mention notification")

    return await _annotation_to_read(ann, db)


@deliverable_router.post(
    "/annotations/{annotation_id}/resolve",
    response_model=AnnotationRead,
)
async def resolve_annotation(
    annotation_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> AnnotationRead:
    from datetime import UTC, datetime

    ann = await _require_annotation(deliverable_id, annotation_id, workspace, db)
    if ann.status == "resolved":
        raise HTTPException(status_code=400, detail="Annotation zaten çözüldü")
    ann.status = "resolved"
    ann.resolved_by_id = workspace.user.id
    ann.resolved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(ann)

    if ann.visibility == "client_visible" and ann.brand_id:
        try:
            from app.services.notification_dispatcher import NotificationDispatcher

            brief = await _require_brief(ann.brief_id, workspace, db)
            deliverable = await _require_deliverable(
                ann.brief_id, ann.deliverable_id, workspace, db
            )
            dispatcher = NotificationDispatcher(db)
            recipients = [u.id for u in await dispatcher.get_brand_members(ann.brand_id)]
            await dispatcher.emit(
                NotificationEventType.ANNOTATION_RESOLVED.value,
                payload={
                    "brief_id": str(ann.brief_id),
                    "brief_title": brief.title,
                    "deliverable_id": str(deliverable.id),
                    "deliverable_title": deliverable.title,
                    "annotation_id": str(ann.id),
                    "label_number": ann.label_number,
                    "agency_name": workspace.agency.name,
                    "summary": (
                        f"{deliverable.title} üzerindeki #{ann.label_number} "
                        "numaralı revizyon çözüldü"
                    ),
                },
                agency_id=workspace.agency.id,
                brand_id=ann.brand_id,
                actor_user_id=workspace.user.id,
                recipient_ids=recipients,
            )
        except Exception:
            logger.exception("Failed to dispatch annotation.resolved notification")

    return await _annotation_to_read(ann, db)


@deliverable_router.post(
    "/annotations/{annotation_id}/reopen",
    response_model=AnnotationRead,
)
async def reopen_annotation(
    annotation_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> AnnotationRead:
    """Reopening a resolved revision is a brand-only action.

    Only the brand user who owns the deliverable may reopen it, via
    ``brand_portal.reopen_brand_annotation``. Agency workspace members are
    never authorized to reopen — this endpoint exists solely to answer
    agency-originated reopen requests with an explicit 403 instead of a
    silent state change.
    """
    raise HTTPException(
        status_code=403,
        detail="Yeniden açma yetkisi yalnızca marka kullanıcısına aittir",
    )


@deliverable_router.post(
    "/annotations/{annotation_id}/replies",
    response_model=AnnotationReplyRead,
    status_code=201,
)
async def add_annotation_reply(
    annotation_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    data: AnnotationReplyCreate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> AnnotationReplyRead:
    ann = await _require_annotation(deliverable_id, annotation_id, workspace, db)

    reply = AnnotationReply(
        annotation_id=ann.id,
        author_user_id=workspace.user.id,
        author_name=workspace.user.full_name,
        body=data.body.strip(),
        body_html=sanitize_html(data.body_html),
        visibility=data.visibility,
    )
    db.add(reply)
    await db.commit()
    await db.refresh(reply)

    if reply.visibility == "client_visible" and ann.brand_id:
        try:
            from app.services.notification_dispatcher import NotificationDispatcher

            brief = await _require_brief(ann.brief_id, workspace, db)
            deliverable = await _require_deliverable(
                ann.brief_id, ann.deliverable_id, workspace, db
            )
            dispatcher = NotificationDispatcher(db)
            recipients = [u.id for u in await dispatcher.get_brand_members(ann.brand_id)]
            await dispatcher.emit(
                NotificationEventType.ANNOTATION_REPLIED.value,
                payload={
                    "brief_id": str(ann.brief_id),
                    "brief_title": brief.title,
                    "deliverable_id": str(deliverable.id),
                    "deliverable_title": deliverable.title,
                    "annotation_id": str(ann.id),
                    "label_number": ann.label_number,
                    "agency_name": workspace.agency.name,
                    "summary": (
                        f"{deliverable.title} üzerindeki #{ann.label_number} "
                        "numaralı revizyona yanıt geldi"
                    ),
                },
                agency_id=workspace.agency.id,
                brand_id=ann.brand_id,
                actor_user_id=workspace.user.id,
                recipient_ids=recipients,
            )
        except Exception:
            logger.exception("Failed to dispatch annotation.replied notification")

    reply_mentions = []
    if data.mentioned_user_ids:
        try:
            brief_for_mentions = await _require_brief(ann.brief_id, workspace, db)
            deliverable_for_mentions = await _require_deliverable(
                ann.brief_id, ann.deliverable_id, workspace, db
            )
            await MentionService(db).sync_mentions_for_source(
                agency_id=workspace.agency.id,
                brand_id=ann.brand_id,
                brief_id=ann.brief_id,
                deliverable_id=ann.deliverable_id,
                source_type="annotation_reply",
                source_id=reply.id,
                actor_user_id=workspace.user.id,
                actor_name=workspace.user.full_name,
                body_text=reply.body,
                mentioned_user_ids=data.mentioned_user_ids,
                portal="agency",
                notification_event_type=NotificationEventType.MENTIONED_IN_ANNOTATION.value,
                notification_payload_extra={
                    "brief_id": str(ann.brief_id),
                    "brief_title": brief_for_mentions.title,
                    "deliverable_id": str(ann.deliverable_id),
                    "deliverable_title": deliverable_for_mentions.title,
                    "annotation_id": str(ann.id),
                    "label_number": ann.label_number,
                    "summary": (
                        f"{workspace.user.full_name} sizi bir revizyon yanıtında etiketledi"
                    ),
                },
            )
            await db.commit()
            reply_mentions = await MentionService(db).get_inline_mentions(
                source_type="annotation_reply", source_id=reply.id
            )
        except Exception:
            logger.exception("Failed to dispatch annotation reply mention notification")

    return AnnotationReplyRead.model_validate(reply).model_copy(update={"mentions": reply_mentions})

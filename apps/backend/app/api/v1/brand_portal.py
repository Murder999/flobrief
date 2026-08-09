"""Brand portal API — scoped to the authenticated brand_user's brand.

All data is filtered to the brand's own data. Agency-internal comments and
internal files are excluded. No X-Agency-ID header is required.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.brand_portal_auth import BrandPortalContext, get_brand_portal_context
from app.core.config import settings
from app.core.rate_limiter import rate_limit_mention_candidates
from app.core.rbac import Permission
from app.db.session import get_db
from app.models.activity import ActivityLog
from app.models.agency import Agency
from app.models.approval import Approval
from app.models.asset import Asset, AssetLink
from app.models.brief import Brief
from app.models.comment import Comment, CommentThread
from app.models.enums import ApprovalStatus, BrandMemberRole, NotificationEventType
from app.models.notification import Notification
from app.models.report import Report
from app.models.user import User
from app.repositories.brand_member import BrandMemberRepository
from app.repositories.invitation import InvitationRepository
from app.repositories.notification import NotificationEventRepository, NotificationRepository
from app.schemas.asset import AssetRead
from app.schemas.brand_identity import (
    BrandDNASummary,
    BrandIdentityDocumentRead,
    BrandIdentityOverview,
    BrandIdentityProfileRead,
    BrandIdentityProfileUpdate,
)
from app.schemas.brief import BriefListResponse, BriefRead
from app.schemas.brief import _check_date_order as _check_brief_date_order
from app.schemas.invitation import BrandInviteRequest, InvitationRead
from app.schemas.mention import MentionCandidateListResponse, MentionInline, validate_mention_count
from app.schemas.notification import (
    NotificationListResponse,
    NotificationRead,
    NotificationRealtimeTicketRead,
)
from app.schemas.onboarding import OnboardingProgressRead, OnboardingStepRead
from app.schemas.report import ReportRead
from app.schemas.whatsapp_test_send import WhatsAppTestSendResponse
from app.services.asset_service import AssetService
from app.services.brand_approval_service import BrandApprovalDecisionService
from app.services.brand_calendar_service import BrandCalendarEntry, build_brand_calendar_agenda
from app.services.deliverable_versioning import get_latest_version_ids_for_brief
from app.services.entitlement_service import EntitlementService
from app.services.invitation_service import InvitationService
from app.services.mention_service import MentionService
from app.services.notification_realtime import (
    NotificationConnectionClaims,
    RealtimeUnavailableError,
    issue_ticket,
    queue_notification_signal,
)
from app.services.onboarding_service import (
    OnboardingService,
    ProgressView,
    default_onboarding_type_for_brand_role,
)

brand_portal_router = APIRouter(prefix="/brand-portal", tags=["brand-portal"])
logger = logging.getLogger(__name__)


# ── Response schemas ──────────────────────────────────────────────────────────


class BrandPortalMeResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    user_type: str
    brand_id: uuid.UUID
    brand_name: str
    brand_slug: str
    brand_status: str
    membership_role: str


class BrandPortalDashboard(BaseModel):
    total_briefs: int
    pending_approval: int
    revision_requested: int
    approved: int
    recent_briefs: list[BriefRead]


class BrandProfileRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    agency_id: uuid.UUID | None


class BrandProfileUpdate(BaseModel):
    name: str | None = None


class UserProfileUpdate(BaseModel):
    full_name: str | None = None
    job_title: str | None = None


class UserProfileRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    job_title: str | None = None
    user_type: str


class BrandBriefCreate(BaseModel):
    title: str
    template_id: uuid.UUID | None = None
    description: str | None = None
    description_html: str | None = None
    campaign_goal: str | None = None
    target_audience: str | None = None
    platforms: list[str] = []
    content_type: str | None = None  # legacy singular, kept for old clients
    content_types: list[str] = []
    priority: str = "normal"
    start_date: str | None = None
    draft_date: str | None = None
    feedback_date: str | None = None
    deadline: str | None = None
    publish_date: str | None = None
    cta: str | None = None
    key_message: str | None = None
    mandatory_messages: str | None = None
    things_to_avoid: str | None = None
    success_criteria: str | None = None
    technical_requirements: str | None = None
    brand_tone: str | None = None
    reference_links: list[str] = []
    additional_notes: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Brief başlığı boş olamaz")
        if len(v) > 500:
            raise ValueError("Brief başlığı 500 karakterden fazla olamaz")
        return v

    @field_validator("start_date", "draft_date", "feedback_date", "deadline", "publish_date")
    @classmethod
    def date_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Tarih YYYY-MM-DD formatında olmalıdır")
        return v

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, v: str) -> str:
        if v not in {"low", "normal", "high", "urgent"}:
            raise ValueError("Geçersiz öncelik")
        return v

    @model_validator(mode="after")
    def _resolve_content_types_and_order(self) -> BrandBriefCreate:
        if not self.content_types and self.content_type:
            self.content_types = [self.content_type]
        _check_brief_date_order(
            {
                "start_date": self.start_date,
                "draft_date": self.draft_date,
                "feedback_date": self.feedback_date,
                "deadline": self.deadline,
                "publish_date": self.publish_date,
            }
        )
        return self


class BrandBriefUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    description_html: str | None = None
    campaign_goal: str | None = None
    target_audience: str | None = None
    platforms: list[str] | None = None
    content_type: str | None = None  # legacy singular, kept for old clients
    content_types: list[str] | None = None
    priority: str | None = None
    start_date: str | None = None
    draft_date: str | None = None
    feedback_date: str | None = None
    deadline: str | None = None
    publish_date: str | None = None
    cta: str | None = None
    key_message: str | None = None
    mandatory_messages: str | None = None
    things_to_avoid: str | None = None
    success_criteria: str | None = None
    technical_requirements: str | None = None
    brand_tone: str | None = None
    reference_links: list[str] | None = None
    additional_notes: str | None = None

    @model_validator(mode="after")
    def _resolve_content_types_and_order(self) -> BrandBriefUpdate:
        if not self.content_types and self.content_type:
            self.content_types = [self.content_type]
        _check_brief_date_order(
            {
                "start_date": self.start_date,
                "draft_date": self.draft_date,
                "feedback_date": self.feedback_date,
                "deadline": self.deadline,
                "publish_date": self.publish_date,
            }
        )
        return self

    @field_validator("start_date", "draft_date", "feedback_date", "deadline", "publish_date")
    @classmethod
    def date_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Tarih YYYY-MM-DD formatında olmalıdır")
        return v


class BriefWithAssets(BaseModel):
    brief: BriefRead
    assets: list[AssetRead]


class FilesResponse(BaseModel):
    briefs: list[BriefWithAssets]
    total_assets: int


class BrandCommentRead(BaseModel):
    id: uuid.UUID
    body: str
    comment_type: str
    author_name: str | None
    author_user_id: uuid.UUID | None
    is_brand_user: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BrandCommentRequest(BaseModel):
    body: str
    comment_type: str = "general"

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Yorum boş olamaz")
        if len(v) > 10000:
            raise ValueError("Yorum 10000 karakterden fazla olamaz")
        return v

    @field_validator("comment_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in {"general", "revision_note", "approval_note"}:
            raise ValueError("Geçersiz yorum türü")
        return v


class BrandApproveRequest(BaseModel):
    note: str | None = None


class BrandRevisionRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Revizyon nedeni boş olamaz")
        if len(v) > 5000:
            raise ValueError("Revizyon nedeni 5000 karakterden fazla olamaz")
        return v


class BrandRejectRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Red nedeni boş olamaz")
        if len(v) > 5000:
            raise ValueError("Red nedeni 5000 karakterden fazla olamaz")
        return v


class BrandTimelineEntry(BaseModel):
    id: str
    event: str
    label: str
    timestamp: datetime
    actor: str | None = None
    note: str | None = None
    color: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@brand_portal_router.get("/me", response_model=BrandPortalMeResponse)
async def get_me(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
) -> BrandPortalMeResponse:
    return BrandPortalMeResponse(
        user_id=ctx.user.id,
        email=ctx.user.email,
        full_name=ctx.user.full_name,
        user_type=ctx.user.user_type,
        brand_id=ctx.brand.id,
        brand_name=ctx.brand.name,
        brand_slug=ctx.brand.slug,
        brand_status=ctx.brand.status,
        membership_role=ctx.membership.role,
    )


@brand_portal_router.get("/dashboard", response_model=BrandPortalDashboard)
async def get_dashboard(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandPortalDashboard:
    base = and_(
        Brief.brand_id == ctx.brand.id,
        Brief.deleted_at.is_(None),
    )

    def _cnt(q: object) -> object:
        return select(func.count()).select_from(q)  # type: ignore[arg-type]

    total = (await db.execute(_cnt(select(Brief).where(base).subquery()))).scalar_one()
    # pending_approval = briefs waiting for brand action (in_review legacy + ready_for_review new)
    pending = (
        await db.execute(
            _cnt(
                select(Brief)
                .where(and_(base, Brief.status.in_(["in_review", "ready_for_review"])))
                .subquery()
            )
        )
    ).scalar_one()
    revision = (
        await db.execute(
            _cnt(select(Brief).where(and_(base, Brief.status == "revision_requested")).subquery())
        )
    ).scalar_one()
    approved = (
        await db.execute(
            _cnt(select(Brief).where(and_(base, Brief.status == "approved")).subquery())
        )
    ).scalar_one()

    recent_rows = (
        (await db.execute(select(Brief).where(base).order_by(Brief.updated_at.desc()).limit(5)))
        .scalars()
        .all()
    )

    return BrandPortalDashboard(
        total_briefs=total,
        pending_approval=pending,
        revision_requested=revision,
        approved=approved,
        recent_briefs=[BriefRead.model_validate(b) for b in recent_rows],
    )


@brand_portal_router.post("/briefs", response_model=BriefRead, status_code=201)
async def create_brand_brief(
    data: BrandBriefCreate,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BriefRead:
    """Brand manager creates a new brief request (saved as draft initially)."""
    if not ctx.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Brief talebi oluşturma yetkisi yalnızca marka yöneticisine aittir",
        )

    meta: dict[str, Any] = {
        "campaign_goal": data.campaign_goal,
        "target_audience": data.target_audience,
        "platforms": data.platforms,
        "content_type": data.content_type,
        "content_types": data.content_types,
        "cta": data.cta,
        "key_message": data.key_message,
        "mandatory_messages": data.mandatory_messages,
        "things_to_avoid": data.things_to_avoid,
        "success_criteria": data.success_criteria,
        "technical_requirements": data.technical_requirements,
        "brand_tone": data.brand_tone,
        "reference_links": data.reference_links,
        "publish_date": data.publish_date,
        "additional_notes": data.additional_notes,
    }

    from app.core.html_sanitizer import sanitize_html

    brief = Brief(
        id=uuid.uuid4(),
        agency_id=ctx.brand.agency_id,
        brand_id=ctx.brand.id,
        template_id=None,
        title=data.title,
        description=data.description,
        description_html=sanitize_html(data.description_html),
        status="draft",
        priority=data.priority,
        start_date=data.start_date,
        draft_date=data.draft_date,
        feedback_date=data.feedback_date,
        deadline=data.deadline,
        publish_date=data.publish_date,
        platforms=data.platforms or None,
        content_types=data.content_types or None,
        source="brand_portal",
        meta=meta,
        created_by_id=ctx.user.id,
        updated_by_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(brief)

    log = ActivityLog(
        id=uuid.uuid4(),
        agency_id=ctx.brand.agency_id,
        brand_id=ctx.brand.id,
        actor_user_id=ctx.user.id,
        action="brand_brief.created",
        entity_type="brief",
        entity_id=brief.id,
        meta={"title": data.title, "brand_name": ctx.brand.name},
        created_at=datetime.now(UTC),
    )
    db.add(log)
    await db.commit()
    await db.refresh(brief)
    return BriefRead.model_validate(brief)


@brand_portal_router.patch("/briefs/{brief_id}", response_model=BriefRead)
async def update_brand_brief(
    brief_id: uuid.UUID,
    data: BrandBriefUpdate,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BriefRead:
    """Brand manager updates their own draft brief request."""
    if not ctx.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Brief düzenleme yetkisi yalnızca marka yöneticisine aittir",
        )

    brief = (
        await db.execute(
            select(Brief).where(
                Brief.id == brief_id,
                Brief.brand_id == ctx.brand.id,
                Brief.source == "brand_portal",
                Brief.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief bulunamadı")

    if brief.status not in ("draft",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yalnızca taslak durumdaki brief'ler düzenlenebilir",
        )

    from app.core.html_sanitizer import sanitize_html

    if data.title is not None:
        brief.title = data.title.strip()
    if data.description is not None:
        brief.description = data.description
    if data.description_html is not None:
        brief.description_html = sanitize_html(data.description_html)
    if data.priority is not None:
        brief.priority = data.priority
    if data.start_date is not None:
        brief.start_date = data.start_date
    if data.draft_date is not None:
        brief.draft_date = data.draft_date
    if data.feedback_date is not None:
        brief.feedback_date = data.feedback_date
    if data.deadline is not None:
        brief.deadline = data.deadline
    if data.publish_date is not None:
        brief.publish_date = data.publish_date
    if data.platforms is not None:
        brief.platforms = data.platforms or None
    if data.content_types is not None:
        brief.content_types = data.content_types or None

    current_meta: dict[str, Any] = dict(brief.meta or {})
    meta_fields = (
        "campaign_goal",
        "target_audience",
        "platforms",
        "content_type",
        "content_types",
        "cta",
        "key_message",
        "mandatory_messages",
        "things_to_avoid",
        "success_criteria",
        "technical_requirements",
        "brand_tone",
        "reference_links",
        "publish_date",
        "additional_notes",
    )
    for field in meta_fields:
        val = getattr(data, field)
        if val is not None:
            current_meta[field] = val
    brief.meta = current_meta
    brief.updated_at = datetime.now(UTC)
    brief.updated_by_id = ctx.user.id

    await db.commit()
    await db.refresh(brief)
    return BriefRead.model_validate(brief)


@brand_portal_router.post("/briefs/{brief_id}/submit", response_model=BriefRead)
async def submit_brand_brief(
    brief_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BriefRead:
    """Brand manager submits a draft brief request to the agency for review."""
    if not ctx.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Brief gönderme yetkisi yalnızca marka yöneticisine aittir",
        )

    brief = (
        await db.execute(
            select(Brief).where(
                Brief.id == brief_id,
                Brief.brand_id == ctx.brand.id,
                Brief.source == "brand_portal",
                Brief.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief bulunamadı")

    if brief.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Brief gönderilemez (mevcut durum: {brief.status})",
        )

    brief.status = "submitted"
    brief.updated_at = datetime.now(UTC)
    brief.updated_by_id = ctx.user.id

    log = ActivityLog(
        id=uuid.uuid4(),
        agency_id=ctx.brand.agency_id,
        brand_id=ctx.brand.id,
        actor_user_id=ctx.user.id,
        action="brand_brief.submitted",
        entity_type="brief",
        entity_id=brief.id,
        meta={"title": brief.title, "brand_name": ctx.brand.name},
        created_at=datetime.now(UTC),
    )
    db.add(log)

    from app.services.notification_dispatcher import NotificationDispatcher

    await NotificationDispatcher(db).emit(
        NotificationEventType.BRIEF_REQUESTED.value,
        payload={
            "brief_id": str(brief.id),
            "brief_title": brief.title,
            "brand_name": ctx.brand.name,
            "summary": f"{ctx.brand.name} yeni brief talebi gönderdi: {brief.title}",
        },
        agency_id=ctx.brand.agency_id,
        brand_id=ctx.brand.id,
        actor_user_id=ctx.user.id,
    )

    await db.commit()
    await db.refresh(brief)
    return BriefRead.model_validate(brief)


@brand_portal_router.get("/briefs", response_model=BriefListResponse)
async def list_briefs(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BriefListResponse:
    base = and_(
        Brief.brand_id == ctx.brand.id,
        Brief.deleted_at.is_(None),
    )
    q = select(Brief).where(base)
    if status:
        q = q.where(Brief.status == status)
    if search:
        q = q.where(Brief.title.ilike(f"%{search}%"))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (
        (await db.execute(q.order_by(Brief.updated_at.desc()).offset(offset).limit(limit)))
        .scalars()
        .all()
    )

    return BriefListResponse(
        items=[BriefRead.model_validate(b) for b in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@brand_portal_router.get("/briefs/{brief_id}", response_model=BriefRead)
async def get_brief(
    brief_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BriefRead:
    result = await db.execute(
        select(Brief).where(
            Brief.id == brief_id,
            Brief.brand_id == ctx.brand.id,
            Brief.deleted_at.is_(None),
        )
    )
    brief = result.scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief bulunamadı")
    return BriefRead.model_validate(brief)


_APPROVAL_STATUS_FILTERS = {
    "pending": [ApprovalStatus.PENDING.value],
    "approved": [ApprovalStatus.APPROVED.value],
    "revision_requested": [ApprovalStatus.REVISION_REQUESTED.value],
    "rejected": [ApprovalStatus.REJECTED.value],
    "expired": [ApprovalStatus.EXPIRED.value],
}


class BrandApprovalCard(BaseModel):
    id: uuid.UUID
    brief_id: uuid.UUID
    brief_title: str
    content_types: list[str]
    platforms: list[str]
    status: str
    agency_name: str | None
    requested_by_name: str | None
    created_at: datetime
    due_date: str | None
    decided_at: datetime | None
    comment_count: int
    assigned_to_me: bool

    model_config = {"from_attributes": True}


@brand_portal_router.get("/approvals", response_model=list[BrandApprovalCard])
async def list_approvals(
    status_filter: str | None = Query(default=None, alias="status"),
    assigned_to_me: bool = Query(default=False),
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[BrandApprovalCard]:
    brief_ids_result = await db.execute(
        select(Brief.id).where(
            Brief.brand_id == ctx.brand.id,
            Brief.deleted_at.is_(None),
        )
    )
    brand_brief_ids = [r for (r,) in brief_ids_result.all()]
    if not brand_brief_ids:
        return []

    q = select(Approval).where(Approval.brief_id.in_(brand_brief_ids))
    if status_filter and status_filter in _APPROVAL_STATUS_FILTERS:
        q = q.where(Approval.status.in_(_APPROVAL_STATUS_FILTERS[status_filter]))
    if assigned_to_me:
        q = q.where(Approval.assigned_to_user_id == ctx.user.id)
    approvals = (await db.execute(q.order_by(Approval.created_at.desc()))).scalars().all()
    if not approvals:
        return []

    brief_by_id = {
        b.id: b
        for b in (
            await db.execute(select(Brief).where(Brief.id.in_({a.brief_id for a in approvals})))
        ).scalars()
    }
    agency = await db.get(Agency, ctx.brand.agency_id)
    requester_ids = {a.requested_by_id for a in approvals}
    requesters = {
        u.id: u.full_name
        for u in (await db.execute(select(User).where(User.id.in_(requester_ids)))).scalars()
    }
    comment_counts: dict[uuid.UUID, int] = {}
    for a in approvals:
        thread = (
            await db.execute(
                select(CommentThread.id).where(
                    CommentThread.brief_id == a.brief_id,
                    CommentThread.brand_id == ctx.brand.id,
                    CommentThread.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if thread is None:
            comment_counts[a.id] = 0
            continue
        count = (
            await db.execute(select(func.count(Comment.id)).where(Comment.thread_id == thread))
        ).scalar_one()
        comment_counts[a.id] = count or 0

    cards: list[BrandApprovalCard] = []
    for a in approvals:
        brief = brief_by_id.get(a.brief_id)
        if brief is None:
            continue
        cards.append(
            BrandApprovalCard(
                id=a.id,
                brief_id=brief.id,
                brief_title=brief.title,
                content_types=brief.content_types or [],
                platforms=brief.platforms or [],
                status=a.status,
                agency_name=agency.name if agency else None,
                requested_by_name=requesters.get(a.requested_by_id),
                created_at=a.created_at,
                due_date=brief.deadline,
                decided_at=a.decided_at,
                comment_count=comment_counts.get(a.id, 0),
                assigned_to_me=a.assigned_to_user_id == ctx.user.id,
            )
        )
    return cards


@brand_portal_router.get("/approvals/{approval_id}", response_model=BrandApprovalCard)
async def get_approval_detail(
    approval_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandApprovalCard:
    approval = await db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Onay bulunamadı")
    brief = await db.get(Brief, approval.brief_id)
    if brief is None or brief.brand_id != ctx.brand.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Onay bulunamadı")

    agency = await db.get(Agency, ctx.brand.agency_id)
    requester = await db.get(User, approval.requested_by_id)
    thread = (
        await db.execute(
            select(CommentThread.id).where(
                CommentThread.brief_id == brief.id,
                CommentThread.brand_id == ctx.brand.id,
                CommentThread.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    comment_count = 0
    if thread is not None:
        comment_count = (
            await db.execute(select(func.count(Comment.id)).where(Comment.thread_id == thread))
        ).scalar_one() or 0

    return BrandApprovalCard(
        id=approval.id,
        brief_id=brief.id,
        brief_title=brief.title,
        content_types=brief.content_types or [],
        platforms=brief.platforms or [],
        status=approval.status,
        agency_name=agency.name if agency else None,
        requested_by_name=requester.full_name if requester else None,
        created_at=approval.created_at,
        due_date=brief.deadline,
        decided_at=approval.decided_at,
        comment_count=comment_count,
        assigned_to_me=approval.assigned_to_user_id == ctx.user.id,
    )


@brand_portal_router.post(
    "/approvals/{approval_id}/comment", response_model=BrandCommentRead, status_code=201
)
async def add_approval_comment(
    approval_id: uuid.UUID,
    data: BrandCommentRequest,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandCommentRead:
    """Comment on the brief behind an approval (tenant-scoped via add_brief_comment)."""
    approval = await db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Onay bulunamadı")
    return await add_brief_comment(approval.brief_id, data, ctx, db)


class BrandTeamMemberRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    role: str
    status: str
    joined_at: datetime | None

    model_config = {"from_attributes": True}


class BrandTeamResponse(BaseModel):
    members: list[BrandTeamMemberRead]
    pending_invitations: list[InvitationRead]


def _require_brand_manager(ctx: BrandPortalContext) -> None:
    if not ctx.is_manager:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Bu işlem yalnızca marka yöneticisine aittir"
        )


@brand_portal_router.get("/team", response_model=BrandTeamResponse)
async def get_team(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandTeamResponse:
    _require_brand_manager(ctx)
    members = await BrandMemberRepository(db).list_by_brand(ctx.brand.id)
    user_ids = {m.user_id for m in members}
    users = (
        {u.id: u for u in (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars()}
        if user_ids
        else {}
    )
    member_reads = [
        BrandTeamMemberRead(
            id=m.id,
            user_id=m.user_id,
            full_name=users[m.user_id].full_name if m.user_id in users else "",
            email=users[m.user_id].email if m.user_id in users else "",
            role=m.role,
            status=m.status,
            joined_at=m.joined_at,
        )
        for m in members
    ]
    invitations = await InvitationRepository(db).list_by_brand(ctx.brand.id)
    pending = [InvitationRead.model_validate(i) for i in invitations if i.is_pending]
    return BrandTeamResponse(members=member_reads, pending_invitations=pending)


@brand_portal_router.get("/team/usage")
async def get_team_usage(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_brand_manager(ctx)
    return await EntitlementService(db).get_brand_usage_summary(ctx.brand.agency_id, ctx.brand.id)


@brand_portal_router.post("/team/invite", status_code=201)
async def invite_team_member(
    data: BrandInviteRequest,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead:
    _require_brand_manager(ctx)
    invitation, _token = await InvitationService(db).create_brand_invite(
        ctx.brand.id, ctx.brand.agency_id, data, ctx.user
    )
    return InvitationRead.model_validate(invitation)


@brand_portal_router.post("/team/invitations/{invitation_id}/cancel")
async def cancel_team_invitation(
    invitation_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_brand_manager(ctx)
    await InvitationService(db).revoke_by_id(invitation_id, ctx.user)
    return {"message": "Davet iptal edildi"}


@brand_portal_router.post("/team/invitations/{invitation_id}/resend")
async def resend_team_invitation(
    invitation_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead:
    _require_brand_manager(ctx)
    invitation, _token = await InvitationService(db).resend_by_id(invitation_id, ctx.user)
    return InvitationRead.model_validate(invitation)


async def _to_brand_reads(items: list[Notification], db: AsyncSession) -> list[NotificationRead]:
    """Attach a safe, precomputed action_url to each brand-portal notification."""
    from app.services.notification_routes import build_notification_action_url

    event_repo = NotificationEventRepository(db)
    event_ids = [n.event_id for n in items if n.event_id is not None]
    events_by_id = await event_repo.get_by_ids(event_ids)
    reads: list[NotificationRead] = []
    for n in items:
        event = events_by_id.get(n.event_id) if n.event_id else None
        action_url = (
            build_notification_action_url(event.event_type, event.payload, "brand")
            if event is not None
            else None
        )
        base = NotificationRead.model_validate(n)
        reads.append(base.model_copy(update={"action_url": action_url}))
    return reads


async def _to_brand_read(notif: Notification, db: AsyncSession) -> NotificationRead:
    reads = await _to_brand_reads([notif], db)
    return reads[0]


@brand_portal_router.post(
    "/notifications/realtime-ticket",
    response_model=NotificationRealtimeTicketRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_brand_notification_realtime_ticket(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
) -> NotificationRealtimeTicketRead:
    try:
        ticket = await issue_ticket(
            NotificationConnectionClaims(
                user_id=str(ctx.user.id),
                portal="brand",
                brand_id=str(ctx.brand.id),
            )
        )
    except RealtimeUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canlı bildirim bağlantısı şu anda kullanılamıyor",
        ) from exc
    return NotificationRealtimeTicketRead(
        ticket=ticket,
        expires_in_seconds=settings.NOTIFICATION_WS_TICKET_TTL_SECONDS,
        websocket_path="/api/v1/notifications/realtime",
    )


@brand_portal_router.get("/notifications", response_model=NotificationListResponse)
async def list_brand_notifications(
    unread_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """Notifications scoped to this brand user AND this brand — no cross-brand leakage."""
    repo = NotificationRepository(db)
    items = await repo.list_for_user(
        user_id=ctx.user.id,
        brand_id=ctx.brand.id,
        unread_only=unread_only,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    unread_count = await repo.count_unread(user_id=ctx.user.id, brand_id=ctx.brand.id)
    return NotificationListResponse(
        items=await _to_brand_reads(items, db),
        unread_count=unread_count,
    )


@brand_portal_router.post("/notifications/{notification_id}/read", response_model=NotificationRead)
async def mark_brand_notification_read(
    notification_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> NotificationRead:
    repo = NotificationRepository(db)
    notif = await repo.get_by_id(notification_id, ctx.user.id)
    if notif is None or notif.brand_id != ctx.brand.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bildirim bulunamadı")
    await repo.mark_read(notif)
    queue_notification_signal(
        db,
        user_id=ctx.user.id,
        agency_id=notif.agency_id,
        brand_id=ctx.brand.id,
    )
    await db.commit()
    await db.refresh(notif)
    return await _to_brand_read(notif, db)


@brand_portal_router.post("/notifications/read-all")
async def mark_all_brand_notifications_read(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    repo = NotificationRepository(db)
    count = await repo.mark_all_read(user_id=ctx.user.id, brand_id=ctx.brand.id)
    if count:
        queue_notification_signal(
            db,
            user_id=ctx.user.id,
            agency_id=None,
            brand_id=ctx.brand.id,
        )
    await db.commit()
    return {"marked_read": count}


@brand_portal_router.post(
    "/notifications/{notification_id}/archive", response_model=NotificationRead
)
async def archive_brand_notification(
    notification_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> NotificationRead:
    repo = NotificationRepository(db)
    notif = await repo.get_by_id(notification_id, ctx.user.id)
    if notif is None or notif.brand_id != ctx.brand.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bildirim bulunamadı")
    await repo.archive(notif)
    queue_notification_signal(
        db,
        user_id=ctx.user.id,
        agency_id=notif.agency_id,
        brand_id=ctx.brand.id,
    )
    await db.commit()
    await db.refresh(notif)
    return await _to_brand_read(notif, db)


@brand_portal_router.post("/notifications/whatsapp/test", response_model=WhatsAppTestSendResponse)
async def send_brand_whatsapp_test_notification(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> WhatsAppTestSendResponse:
    """Self-service controlled WhatsApp test send for brand-portal users —
    mirrors the agency-side /notifications/whatsapp/test endpoint. Takes no
    request body; the recipient is always the caller's own opted-in number
    (see whatsapp_test_send_service.send_test_message)."""
    agency = await db.get(Agency, ctx.brand.agency_id)
    if agency is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ajans bulunamadı")

    from app.services.whatsapp_test_send_service import send_test_message

    outcome = await send_test_message(db, agency=agency, user=ctx.user)
    return WhatsAppTestSendResponse(
        delivery_id=outcome.delivery_id,
        masked_recipient=outcome.masked_recipient,
        status=outcome.status,
        provider=outcome.provider,
        template_key=outcome.template_key,
        provider_message_id=outcome.provider_message_id,
        safe_error=outcome.safe_error,
    )


class _BrandAssetAgencyAdapter:
    def __init__(self, agency_id: uuid.UUID) -> None:
        self.id = agency_id


class _BrandAssetWorkspaceAdapter:
    """Duck-types WorkspaceContext's `.agency.id`/`.user` surface so AssetService
    (built for the agency workspace) can be reused for brand-portal uploads."""

    def __init__(self, ctx: BrandPortalContext) -> None:
        self.agency = _BrandAssetAgencyAdapter(ctx.brand.agency_id)
        self.user = ctx.user


def _brand_asset_service(db: AsyncSession, ctx: BrandPortalContext) -> AssetService:
    return AssetService(db, _BrandAssetWorkspaceAdapter(ctx))  # type: ignore[arg-type]


@brand_portal_router.post("/briefs/{brief_id}/assets", response_model=AssetRead, status_code=201)
async def upload_brand_brief_asset(
    brief_id: uuid.UUID,
    file: UploadFile = File(...),
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> AssetRead:
    return await _brand_asset_service(db, ctx).upload_brand_reference(
        brief_id,
        ctx.brand.id,
        file,
    )


@brand_portal_router.get("/briefs/{brief_id}/assets", response_model=list[AssetRead])
async def list_brand_brief_assets(
    brief_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[AssetRead]:
    return await _brand_asset_service(db, ctx).list_for_brand_brief(
        brief_id,
        ctx.brand.id,
    )


@brand_portal_router.delete("/assets/{asset_id}")
async def delete_brand_brief_asset(
    asset_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _brand_asset_service(db, ctx).delete_brand_reference(asset_id, ctx.brand.id)
    return Response(status_code=204)


@brand_portal_router.get("/calendar", response_model=list[BrandCalendarEntry])
async def list_calendar(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    entry_status: str | None = Query(default=None, alias="status"),
    event_type: str | None = Query(default=None, alias="event_type"),
    brief_id: uuid.UUID | None = Query(default=None, alias="brief_id"),
    assignee_id: uuid.UUID | None = Query(default=None, alias="assignee_id"),
    priority: str | None = Query(default=None, alias="priority"),
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[BrandCalendarEntry]:
    return await build_brand_calendar_agenda(
        db,
        ctx.brand.id,
        date_from=from_date,
        date_to=to_date,
        status=entry_status,
        event_type=event_type,
        brief_id=brief_id,
        assignee_id=assignee_id,
        priority=priority,
    )


@brand_portal_router.get("/files", response_model=FilesResponse)
async def list_files(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> FilesResponse:
    # Get brand's briefs
    brief_rows = (
        (
            await db.execute(
                select(Brief)
                .where(
                    Brief.brand_id == ctx.brand.id,
                    Brief.deleted_at.is_(None),
                )
                .order_by(Brief.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )

    result_briefs: list[BriefWithAssets] = []
    total_assets = 0

    for brief in brief_rows:
        # Assets linked to this brief (client-visible only: brand_id matches)
        link_rows = (
            (await db.execute(select(AssetLink).where(AssetLink.brief_id == brief.id)))
            .scalars()
            .all()
        )

        asset_ids = [lnk.asset_id for lnk in link_rows]
        if not asset_ids:
            result_briefs.append(
                BriefWithAssets(
                    brief=BriefRead.model_validate(brief),
                    assets=[],
                )
            )
            continue

        asset_rows = (
            (
                await db.execute(
                    select(Asset).where(
                        Asset.id.in_(asset_ids),
                        Asset.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )

        assets = [AssetRead.model_validate(a) for a in asset_rows]
        total_assets += len(assets)
        result_briefs.append(
            BriefWithAssets(
                brief=BriefRead.model_validate(brief),
                assets=assets,
            )
        )

    return FilesResponse(briefs=result_briefs, total_assets=total_assets)


@brand_portal_router.get("/reports", response_model=list[ReportRead])
async def list_reports(
    limit: int = Query(default=50, ge=1, le=200),
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[ReportRead]:
    rows = (
        (
            await db.execute(
                select(Report)
                .where(
                    Report.brand_id == ctx.brand.id,
                    Report.deleted_at.is_(None),
                )
                .order_by(Report.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [ReportRead.model_validate(r) for r in rows]


@brand_portal_router.get("/profile", response_model=UserProfileRead)
async def get_profile(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
) -> UserProfileRead:
    return UserProfileRead(
        id=ctx.user.id,
        email=ctx.user.email,
        full_name=ctx.user.full_name,
        job_title=ctx.user.job_title,
        user_type=ctx.user.user_type,
    )


@brand_portal_router.patch("/profile", response_model=UserProfileRead)
async def update_profile(
    data: UserProfileUpdate,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> UserProfileRead:
    if data.full_name is not None:
        full_name = data.full_name.strip()
        if not full_name:
            raise HTTPException(status_code=422, detail="İsim boş olamaz")
        ctx.user.full_name = full_name
    if data.job_title is not None:
        ctx.user.job_title = data.job_title.strip() or None

    await db.flush()
    await db.refresh(ctx.user)

    return UserProfileRead(
        id=ctx.user.id,
        email=ctx.user.email,
        full_name=ctx.user.full_name,
        job_title=ctx.user.job_title,
        user_type=ctx.user.user_type,
    )


@brand_portal_router.get("/brand", response_model=BrandProfileRead)
async def get_brand_profile(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
) -> BrandProfileRead:
    return BrandProfileRead(
        id=ctx.brand.id,
        name=ctx.brand.name,
        slug=ctx.brand.slug,
        status=ctx.brand.status,
        agency_id=ctx.brand.agency_id,
    )


@brand_portal_router.get("/briefs/{brief_id}/comments", response_model=list[BrandCommentRead])
async def list_brief_comments(
    brief_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[BrandCommentRead]:
    """Returns client_visible comments on this brief. Internal agency comments are excluded."""
    brief = (
        await db.execute(
            select(Brief).where(
                Brief.id == brief_id,
                Brief.brand_id == ctx.brand.id,
                Brief.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief bulunamadı")

    threads = (
        (
            await db.execute(
                select(CommentThread).where(
                    CommentThread.brief_id == brief_id,
                    CommentThread.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )

    if not threads:
        return []

    thread_ids = [t.id for t in threads]
    comments = (
        (
            await db.execute(
                select(Comment)
                .where(
                    Comment.thread_id.in_(thread_ids),
                    Comment.visibility == "client_visible",
                    Comment.deleted_at.is_(None),
                )
                .order_by(Comment.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    result = []
    for c in comments:
        meta = c.author_name or ""
        comment_type = "general"
        if c.author_email and c.author_email.startswith("revision:"):
            comment_type = "revision_note"
        elif c.author_email and c.author_email.startswith("approval:"):
            comment_type = "approval_note"
        result.append(
            BrandCommentRead(
                id=c.id,
                body=c.body,
                comment_type=comment_type,
                author_name=meta or None,
                author_user_id=c.author_user_id,
                is_brand_user=True,
                created_at=c.created_at,
            )
        )
    return result


@brand_portal_router.post(
    "/briefs/{brief_id}/comments", response_model=BrandCommentRead, status_code=201
)
async def add_brief_comment(
    brief_id: uuid.UUID,
    data: BrandCommentRequest,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandCommentRead:
    """Brand user adds a client_visible comment to a brief."""
    brief = (
        await db.execute(
            select(Brief).where(
                Brief.id == brief_id,
                Brief.brand_id == ctx.brand.id,
                Brief.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief bulunamadı")

    # Find or create the brand comment thread for this brief
    thread = (
        await db.execute(
            select(CommentThread).where(
                CommentThread.brief_id == brief_id,
                CommentThread.brand_id == ctx.brand.id,
                CommentThread.thread_type == "brief",
                CommentThread.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if thread is None:
        thread = CommentThread(
            id=uuid.uuid4(),
            agency_id=brief.agency_id,
            brand_id=ctx.brand.id,
            brief_id=brief_id,
            thread_type="brief",
            status="open",
            created_by_id=ctx.user.id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(thread)
        await db.flush()

    type_prefix = {
        "revision_note": "revision:",
        "approval_note": "approval:",
    }.get(data.comment_type, "")

    comment = Comment(
        id=uuid.uuid4(),
        thread_id=thread.id,
        author_user_id=ctx.user.id,
        author_name=ctx.user.full_name,
        author_email=f"{type_prefix}{ctx.user.email}" if type_prefix else ctx.user.email,
        body=data.body,
        visibility="client_visible",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(comment)

    log = ActivityLog(
        id=uuid.uuid4(),
        agency_id=brief.agency_id,
        brand_id=ctx.brand.id,
        actor_user_id=ctx.user.id,
        action="brief.comment_added",
        entity_type="brief",
        entity_id=brief_id,
        meta={"comment_type": data.comment_type, "brand_name": ctx.brand.name},
        created_at=datetime.now(UTC),
    )
    db.add(log)
    await db.commit()

    return BrandCommentRead(
        id=comment.id,
        body=comment.body,
        comment_type=data.comment_type,
        author_name=ctx.user.full_name,
        author_user_id=ctx.user.id,
        is_brand_user=True,
        created_at=comment.created_at,
    )


async def _can_decide_approval(
    ctx: BrandPortalContext, db: AsyncSession, brief_id: uuid.UUID
) -> bool:
    """Owner/manager may decide any approval; external_approver only ones assigned to them."""
    if not ctx.has_permission(Permission.BRIEF_APPROVE):
        return False
    if ctx.membership.role != BrandMemberRole.EXTERNAL_APPROVER.value:
        return True
    result = await db.execute(
        select(Approval.id).where(
            Approval.brief_id == brief_id,
            Approval.status == ApprovalStatus.PENDING.value,
            Approval.assigned_to_user_id == ctx.user.id,
        )
    )
    return result.first() is not None


@brand_portal_router.post("/briefs/{brief_id}/approve", response_model=BriefRead)
async def approve_brief(
    brief_id: uuid.UUID,
    data: BrandApproveRequest,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BriefRead:
    """Brand manager (or assigned approver) approves a brief under review.

    Concurrency-safe: BrandApprovalDecisionService locks the Brief row so two
    simultaneous decisions on the same brief cannot both succeed.
    """
    if not await _can_decide_approval(ctx, db, brief_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Onay yetkiniz yok",
        )
    brief = await BrandApprovalDecisionService(db).decide(brief_id, ctx, "approve", data.note)
    return BriefRead.model_validate(brief)


@brand_portal_router.post("/briefs/{brief_id}/request-revision", response_model=BriefRead)
async def request_revision(
    brief_id: uuid.UUID,
    data: BrandRevisionRequest,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BriefRead:
    """Brand manager (or assigned approver) requests revision on a brief under review."""
    if not await _can_decide_approval(ctx, db, brief_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Revizyon yetkiniz yok",
        )
    brief = await BrandApprovalDecisionService(db).decide(
        brief_id, ctx, "revision_requested", data.reason
    )
    return BriefRead.model_validate(brief)


@brand_portal_router.post("/briefs/{brief_id}/reject", response_model=BriefRead)
async def reject_brief(
    brief_id: uuid.UUID,
    data: BrandRejectRequest,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BriefRead:
    """Brand manager (or assigned approver) rejects a brief under review (terminal state)."""
    if not await _can_decide_approval(ctx, db, brief_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Red yetkiniz yok",
        )
    brief = await BrandApprovalDecisionService(db).decide(brief_id, ctx, "rejected", data.reason)
    return BriefRead.model_validate(brief)


@brand_portal_router.get("/briefs/{brief_id}/timeline", response_model=list[BrandTimelineEntry])
async def get_brief_timeline(
    brief_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[BrandTimelineEntry]:
    """Returns a timeline of key events for a brief."""
    brief = (
        await db.execute(
            select(Brief).where(
                Brief.id == brief_id,
                Brief.brand_id == ctx.brand.id,
                Brief.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief bulunamadı")

    entries: list[BrandTimelineEntry] = []

    # Created
    entries.append(
        BrandTimelineEntry(
            id=f"created-{brief_id}",
            event="created",
            label="Brief oluşturuldu",
            timestamp=brief.created_at,
            color="muted",
        )
    )

    # Activity log entries (brand-visible only)
    logs = (
        (
            await db.execute(
                select(ActivityLog)
                .where(
                    ActivityLog.entity_type == "brief",
                    ActivityLog.entity_id == brief_id,
                    ActivityLog.action.in_(
                        [
                            "brief.approved_by_brand",
                            "brief.revision_requested_by_brand",
                            "brief.comment_added",
                            "brief.status_changed",
                            "brief.sent_to_approval",
                        ]
                    ),
                )
                .order_by(ActivityLog.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    for log in logs:
        meta = log.meta or {}
        if log.action == "brief.sent_to_approval":
            entries.append(
                BrandTimelineEntry(
                    id=str(log.id),
                    event="sent_to_approval",
                    label="Onaya gönderildi",
                    timestamp=log.created_at,
                    color="amber",
                )
            )
        elif log.action == "brief.approved_by_brand":
            entries.append(
                BrandTimelineEntry(
                    id=str(log.id),
                    event="approved",
                    label="Onaylandı",
                    timestamp=log.created_at,
                    actor=meta.get("brand_name"),
                    color="emerald",
                )
            )
        elif log.action == "brief.revision_requested_by_brand":
            entries.append(
                BrandTimelineEntry(
                    id=str(log.id),
                    event="revision_requested",
                    label="Revizyon talep edildi",
                    timestamp=log.created_at,
                    actor=meta.get("brand_name"),
                    note=meta.get("reason"),
                    color="orange",
                )
            )
        elif log.action == "brief.comment_added":
            entries.append(
                BrandTimelineEntry(
                    id=str(log.id),
                    event="comment_added",
                    label="Yorum eklendi",
                    timestamp=log.created_at,
                    actor=meta.get("brand_name"),
                    color="blue",
                )
            )
        elif log.action == "brief.status_changed":
            new_st = meta.get("new_status", "")
            color_map = {
                "in_review": "amber",
                "approved": "emerald",
                "revision_requested": "orange",
                "archived": "muted",
            }
            label_map = {
                "in_review": "İncelemeye alındı",
                "approved": "Onaylandı",
                "revision_requested": "Revizyon istendi",
                "archived": "Arşivlendi",
                "draft": "Taslağa alındı",
            }
            entries.append(
                BrandTimelineEntry(
                    id=str(log.id),
                    event=f"status_{new_st}",
                    label=label_map.get(new_st, f"Durum: {new_st}"),
                    timestamp=log.created_at,
                    color=color_map.get(new_st, "muted"),
                )
            )

    # If status is in_review/approved/revision_requested and no log exists, synthesize
    action_events = {e.event for e in entries}
    no_review = "sent_to_approval" not in action_events and "status_in_review" not in action_events
    if brief.status == "in_review" and no_review:
        entries.append(
            BrandTimelineEntry(
                id=f"status-inreview-{brief_id}",
                event="sent_to_approval",
                label="Onaya gönderildi",
                timestamp=brief.updated_at,
                color="amber",
            )
        )
    elif brief.status == "approved" and "approved" not in action_events:
        entries.append(
            BrandTimelineEntry(
                id=f"status-approved-{brief_id}",
                event="approved",
                label="Onaylandı",
                timestamp=brief.updated_at,
                color="emerald",
            )
        )
    elif brief.status == "revision_requested" and "revision_requested" not in action_events:
        entries.append(
            BrandTimelineEntry(
                id=f"status-revision-{brief_id}",
                event="revision_requested",
                label="Revizyon talep edildi",
                timestamp=brief.updated_at,
                color="orange",
            )
        )

    # Sort chronologically
    entries.sort(key=lambda e: e.timestamp)
    return entries


@brand_portal_router.patch("/brand", response_model=BrandProfileRead)
async def update_brand_profile(
    data: BrandProfileUpdate,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandProfileRead:
    if not ctx.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Marka profilini yalnızca marka yöneticisi düzenleyebilir",
        )

    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Marka adı boş olamaz")
        ctx.brand.name = name

    await db.flush()
    await db.refresh(ctx.brand)

    return BrandProfileRead(
        id=ctx.brand.id,
        name=ctx.brand.name,
        slug=ctx.brand.slug,
        status=ctx.brand.status,
        agency_id=ctx.brand.agency_id,
    )


class BriefTemplateRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    industry: str | None
    is_system_template: bool

    model_config = {"from_attributes": True}


@brand_portal_router.get("/templates", response_model=list[BriefTemplateRead])
async def list_brief_templates(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[BriefTemplateRead]:
    """Returns brief templates available to this brand (system + their agency's templates)."""
    from sqlalchemy import or_

    from app.models.brief_template import BriefTemplate

    rows = (
        (
            await db.execute(
                select(BriefTemplate)
                .where(
                    BriefTemplate.is_active.is_(True),
                    or_(
                        BriefTemplate.is_system_template.is_(True),
                        BriefTemplate.agency_id == ctx.brand.agency_id,
                    ),
                )
                .order_by(BriefTemplate.is_system_template.desc(), BriefTemplate.name.asc())
            )
        )
        .scalars()
        .all()
    )

    return [BriefTemplateRead.model_validate(t) for t in rows]


# ── Brand deliverable endpoints ───────────────────────────────────────────────


class BrandDeliverableAssetRead(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    storage_provider: str
    checksum: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BrandDeliverableRead(BaseModel):
    id: uuid.UUID
    brief_id: uuid.UUID
    title: str
    description: str | None
    description_html: str | None
    deliverable_type: str
    status: str
    version_number: int
    revision_count: int
    revision_note: str | None
    approve_note: str | None
    # True unless another deliverable in this brief shares the same title
    # (normalized) and was submitted/created more recently — computed
    # identically to the agency-side DeliverableRead field, see
    # app/services/deliverable_versioning.py.
    is_latest_version: bool = True
    submitted_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
    assets: list[BrandDeliverableAssetRead] = []
    open_annotation_count: int = 0

    model_config = {"from_attributes": True}


class BrandApproveDeliverableRequest(BaseModel):
    note: str | None = None


class BrandReviseDeliverableRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Revizyon nedeni boş olamaz")
        if len(v) > 5000:
            raise ValueError("Revizyon nedeni 5000 karakterden fazla olamaz")
        return v


async def _get_brand_brief(
    brief_id: uuid.UUID,
    ctx: BrandPortalContext,
    db: AsyncSession,
) -> Brief:
    brief = (
        await db.execute(
            select(Brief).where(
                Brief.id == brief_id,
                Brief.brand_id == ctx.brand.id,
                Brief.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief bulunamadı")
    return brief


async def _get_brand_deliverable_assets(
    deliverable_id: uuid.UUID,
    db: AsyncSession,
) -> list[BrandDeliverableAssetRead]:
    from sqlalchemy import and_

    from app.models.asset import Asset, AssetLink

    rows = (
        (
            await db.execute(
                select(Asset)
                .join(
                    AssetLink,
                    and_(
                        AssetLink.asset_id == Asset.id,
                        AssetLink.deliverable_id == deliverable_id,
                        Asset.deleted_at.is_(None),
                    ),
                )
                .where(Asset.visibility == "client_visible")
                .order_by(Asset.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [BrandDeliverableAssetRead.model_validate(a) for a in rows]


async def _count_open_annotations(
    deliverable_ids: list[uuid.UUID],
    db: AsyncSession,
) -> dict[uuid.UUID, int]:
    """Single grouped query — avoids N+1 across the deliverable list."""
    if not deliverable_ids:
        return {}
    from app.models.deliverable_annotation import DeliverableAnnotation

    rows = (
        await db.execute(
            select(DeliverableAnnotation.deliverable_id, func.count().label("cnt"))
            .where(
                DeliverableAnnotation.deliverable_id.in_(deliverable_ids),
                DeliverableAnnotation.status == "open",
                DeliverableAnnotation.visibility == "client_visible",
                DeliverableAnnotation.deleted_at.is_(None),
            )
            .group_by(DeliverableAnnotation.deliverable_id)
        )
    ).all()
    return {row.deliverable_id: row.cnt for row in rows}


@brand_portal_router.get(
    "/briefs/{brief_id}/deliverables",
    response_model=list[BrandDeliverableRead],
)
async def list_brand_deliverables(
    brief_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[BrandDeliverableRead]:
    """Brand sees only submitted/approved/revision_requested deliverables — not drafts."""
    from app.models.deliverable import Deliverable

    await _get_brand_brief(brief_id, ctx, db)

    rows = (
        (
            await db.execute(
                select(Deliverable)
                .where(
                    Deliverable.brief_id == brief_id,
                    Deliverable.brand_id == ctx.brand.id,
                    Deliverable.status.in_(
                        ["submitted", "approved", "revision_requested", "rejected"]
                    ),
                    Deliverable.deleted_at.is_(None),
                )
                .order_by(Deliverable.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    open_counts = await _count_open_annotations([d.id for d in rows], db)
    # Full-brief fetch (not just the statuses visible to the brand) so a
    # draft sibling the agency hasn't submitted yet still counts toward the
    # same title chain — keeps this identical to the agency-side computation.
    latest_ids = await get_latest_version_ids_for_brief(db, brief_id)

    result = []
    for d in rows:
        assets = await _get_brand_deliverable_assets(d.id, db)
        result.append(
            BrandDeliverableRead(
                id=d.id,
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
                submitted_at=d.submitted_at,
                approved_at=d.approved_at,
                created_at=d.created_at,
                assets=assets,
                open_annotation_count=open_counts.get(d.id, 0),
            )
        )
    return result


@brand_portal_router.post(
    "/briefs/{brief_id}/deliverables/{deliverable_id}/approve",
    response_model=BrandDeliverableRead,
)
async def approve_deliverable(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    data: BrandApproveDeliverableRequest,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandDeliverableRead:
    if not ctx.is_manager:
        raise HTTPException(
            status_code=403,
            detail="Onay yetkisi yalnızca marka yöneticisine aittir",
        )

    from app.models.deliverable import Deliverable

    brief = await _get_brand_brief(brief_id, ctx, db)

    d = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.id == deliverable_id,
                Deliverable.brief_id == brief_id,
                Deliverable.brand_id == ctx.brand.id,
                Deliverable.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if d is None:
        raise HTTPException(status_code=404, detail="Deliverable bulunamadı")

    if d.status != "submitted":
        raise HTTPException(
            status_code=400,
            detail=f"Yalnızca gönderilmiş deliverable onaylanabilir (mevcut: {d.status})",
        )

    latest_ids = await get_latest_version_ids_for_brief(db, brief_id)
    if d.id not in latest_ids:
        raise HTTPException(
            status_code=400,
            detail="Bu deliverable artık güncel sürüm değil; eski sürüm onaylanamaz",
        )

    d.status = "approved"
    d.approve_note = data.note
    d.approved_by_id = ctx.user.id
    d.approved_at = datetime.now(UTC)

    log = ActivityLog(
        id=uuid.uuid4(),
        agency_id=brief.agency_id,
        brand_id=ctx.brand.id,
        actor_user_id=ctx.user.id,
        action="deliverable.approved_by_brand",
        entity_type="deliverable",
        entity_id=d.id,
        meta={"deliverable_title": d.title, "brand_name": ctx.brand.name},
        created_at=datetime.now(UTC),
    )
    db.add(log)
    await db.commit()
    await db.refresh(d)

    try:
        from app.models.enums import NotificationEventType
        from app.services.notification_dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher(db)
        await dispatcher.emit(
            NotificationEventType.DELIVERABLE_APPROVED.value,
            payload={
                "brief_id": str(brief_id),
                "brief_title": brief.title,
                "deliverable_id": str(d.id),
                "deliverable_title": d.title,
                "brand_name": ctx.brand.name,
                "summary": f"Teslimat onaylandı: {d.title}",
            },
            agency_id=brief.agency_id,
            brand_id=ctx.brand.id,
            actor_user_id=ctx.user.id,
        )
    except Exception:
        pass

    assets = await _get_brand_deliverable_assets(d.id, db)
    open_counts = await _count_open_annotations([d.id], db)
    return BrandDeliverableRead(
        id=d.id,
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
        is_latest_version=True,
        submitted_at=d.submitted_at,
        approved_at=d.approved_at,
        created_at=d.created_at,
        assets=assets,
        open_annotation_count=open_counts.get(d.id, 0),
    )


@brand_portal_router.post(
    "/briefs/{brief_id}/deliverables/{deliverable_id}/request-revision",
    response_model=BrandDeliverableRead,
)
async def request_deliverable_revision(
    brief_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    data: BrandReviseDeliverableRequest,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandDeliverableRead:
    if not ctx.is_manager:
        raise HTTPException(
            status_code=403,
            detail="Revizyon yetkisi yalnızca marka yöneticisine aittir",
        )

    from app.models.deliverable import Deliverable

    brief = await _get_brand_brief(brief_id, ctx, db)

    d = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.id == deliverable_id,
                Deliverable.brief_id == brief_id,
                Deliverable.brand_id == ctx.brand.id,
                Deliverable.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if d is None:
        raise HTTPException(status_code=404, detail="Deliverable bulunamadı")

    if d.status != "submitted":
        raise HTTPException(
            status_code=400,
            detail=f"Yalnızca gönderilmiş deliverable revize edilebilir (mevcut: {d.status})",
        )

    latest_ids = await get_latest_version_ids_for_brief(db, brief_id)
    if d.id not in latest_ids:
        raise HTTPException(
            status_code=400,
            detail="Bu deliverable artık güncel sürüm değil; eski sürüme revizyon istenemez",
        )

    d.status = "revision_requested"
    d.revision_note = data.reason
    d.revision_count = (d.revision_count or 0) + 1

    log = ActivityLog(
        id=uuid.uuid4(),
        agency_id=brief.agency_id,
        brand_id=ctx.brand.id,
        actor_user_id=ctx.user.id,
        action="deliverable.revision_requested",
        entity_type="deliverable",
        entity_id=d.id,
        meta={
            "deliverable_title": d.title,
            "reason": data.reason[:200],
            "brand_name": ctx.brand.name,
        },
        created_at=datetime.now(UTC),
    )
    db.add(log)
    await db.commit()
    await db.refresh(d)

    try:
        from app.models.enums import NotificationEventType
        from app.services.notification_dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher(db)
        await dispatcher.emit(
            NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value,
            payload={
                "brief_id": str(brief_id),
                "brief_title": brief.title,
                "deliverable_id": str(d.id),
                "deliverable_title": d.title,
                "brand_name": ctx.brand.name,
                "reason": data.reason[:200],
                "revision_count": d.revision_count,
                "summary": f"Revizyon talep edildi: {d.title}",
            },
            agency_id=brief.agency_id,
            brand_id=ctx.brand.id,
            actor_user_id=ctx.user.id,
        )
    except Exception:
        pass

    assets = await _get_brand_deliverable_assets(d.id, db)
    open_counts = await _count_open_annotations([d.id], db)
    return BrandDeliverableRead(
        id=d.id,
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
        is_latest_version=True,
        submitted_at=d.submitted_at,
        approved_at=d.approved_at,
        created_at=d.created_at,
        assets=assets,
        open_annotation_count=open_counts.get(d.id, 0),
    )


# ── Brand annotation endpoints ─────────────────────────────────────────────────


class BrandAnnotationReplyRead(BaseModel):
    id: uuid.UUID
    annotation_id: uuid.UUID
    author_user_id: uuid.UUID | None
    author_name: str | None
    body: str
    body_html: str | None
    visibility: str
    created_at: datetime
    mentions: list[MentionInline] = []

    model_config = {"from_attributes": True}


class BrandAnnotationRead(BaseModel):
    id: uuid.UUID
    deliverable_id: uuid.UUID
    asset_id: uuid.UUID | None
    version_number: int
    x_percent: float | None
    y_percent: float | None
    label_number: int
    status: str
    annotation_type: str
    visibility: str
    body: str | None
    body_html: str | None
    created_by_id: uuid.UUID | None
    created_by_name: str | None = None
    resolved_at: datetime | None
    created_at: datetime
    replies: list[BrandAnnotationReplyRead] = []
    mentions: list[MentionInline] = []

    model_config = {"from_attributes": True}


class BrandAnnotationCreate(BaseModel):
    asset_id: uuid.UUID | None = None
    version_number: int = 1
    x_percent: float | None = None
    y_percent: float | None = None
    annotation_type: str = "revision"
    body: str
    body_html: str | None = None
    mentioned_user_ids: list[uuid.UUID] = []

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("body cannot be empty")
        if len(v) > 10_000:
            raise ValueError("body must be 10 000 chars or less")
        return v

    @field_validator("annotation_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in {"general", "revision", "approval_note"}:
            raise ValueError("Invalid annotation_type")
        return v

    @field_validator("mentioned_user_ids")
    @classmethod
    def cap_mentions(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        return validate_mention_count(v)


class BrandAnnotationReplyCreate(BaseModel):
    body: str
    body_html: str | None = None
    mentioned_user_ids: list[uuid.UUID] = []

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("body cannot be empty")
        return v

    @field_validator("mentioned_user_ids")
    @classmethod
    def cap_mentions(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        return validate_mention_count(v)


async def _brand_annotation_to_read(
    ann: object,
    db: AsyncSession,
) -> BrandAnnotationRead:
    from app.models.deliverable_annotation import AnnotationReply

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
            BrandAnnotationReplyRead.model_validate(r).model_copy(
                update={"mentions": reply_mentions}
            )
        )
    ann_mentions = await mention_service.get_inline_mentions(
        source_type="annotation", source_id=ann.id
    )
    created_by_name: str | None = None
    if ann.created_by_id is not None:
        creator = await db.get(User, ann.created_by_id)
        created_by_name = creator.full_name if creator else None
    return BrandAnnotationRead(
        id=ann.id,
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
        resolved_at=ann.resolved_at,
        created_at=ann.created_at,
        replies=replies,
        mentions=ann_mentions,
    )


@brand_portal_router.get(
    "/deliverables/{deliverable_id}/annotations",
    response_model=list[BrandAnnotationRead],
)
async def list_brand_annotations(
    deliverable_id: uuid.UUID,
    version_number: int | None = None,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[BrandAnnotationRead]:
    from app.models.deliverable import Deliverable
    from app.models.deliverable_annotation import DeliverableAnnotation

    # Verify deliverable belongs to this brand
    d_result = await db.execute(
        select(Deliverable).where(
            Deliverable.id == deliverable_id,
            Deliverable.brand_id == ctx.brand.id,
            Deliverable.deleted_at.is_(None),
        )
    )
    if not d_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Deliverable bulunamadı")

    q = select(DeliverableAnnotation).where(
        DeliverableAnnotation.deliverable_id == deliverable_id,
        DeliverableAnnotation.brand_id == ctx.brand.id,
        DeliverableAnnotation.deleted_at.is_(None),
        DeliverableAnnotation.visibility == "client_visible",  # Brand never sees internal
    )
    if version_number is not None:
        q = q.where(DeliverableAnnotation.version_number == version_number)
    q = q.order_by(DeliverableAnnotation.label_number.asc())
    rows = await db.execute(q)
    anns = rows.scalars().all()
    return [await _brand_annotation_to_read(a, db) for a in anns]


@brand_portal_router.post(
    "/deliverables/{deliverable_id}/annotations",
    response_model=BrandAnnotationRead,
    status_code=201,
)
async def create_brand_annotation(
    deliverable_id: uuid.UUID,
    data: BrandAnnotationCreate,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandAnnotationRead:
    from app.models.deliverable import Deliverable
    from app.models.deliverable_annotation import DeliverableAnnotation

    d_result = await db.execute(
        select(Deliverable).where(
            Deliverable.id == deliverable_id,
            Deliverable.brand_id == ctx.brand.id,
            Deliverable.status.in_(["submitted", "approved", "revision_requested"]),
            Deliverable.deleted_at.is_(None),
        )
    )
    d = d_result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Deliverable bulunamadı")

    latest_ids = await get_latest_version_ids_for_brief(db, d.brief_id)
    if d.id not in latest_ids:
        raise HTTPException(
            status_code=400,
            detail="Bu deliverable artık güncel sürüm değil; eski sürüme revizyon notu eklenemez",
        )

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
        agency_id=d.agency_id,
        brand_id=ctx.brand.id,
        brief_id=d.brief_id,
        deliverable_id=deliverable_id,
        asset_id=data.asset_id,
        version_number=data.version_number,
        x_percent=data.x_percent,
        y_percent=data.y_percent,
        label_number=next_label,
        status="open",
        annotation_type=data.annotation_type,
        visibility="client_visible",  # Brand annotations are always client_visible
        body=data.body.strip(),
        body_html=data.body_html,
        created_by_id=ctx.user.id,
    )
    db.add(ann)
    await db.commit()
    await db.refresh(ann)

    try:
        from app.services.notification_dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher(db)
        await dispatcher.emit(
            NotificationEventType.ANNOTATION_CREATED.value,
            payload={
                "brief_id": str(d.brief_id),
                "deliverable_id": str(d.id),
                "deliverable_title": d.title,
                "annotation_id": str(ann.id),
                "label_number": ann.label_number,
                "brand_name": ctx.brand.name,
                "summary": (
                    f"{ctx.brand.name}, {d.title} üzerinde yeni bir "
                    f"revizyon notu ekledi (#{ann.label_number})"
                ),
            },
            agency_id=d.agency_id,
            brand_id=ctx.brand.id,
            actor_user_id=ctx.user.id,
        )
    except Exception:
        logger.exception("Failed to dispatch annotation.created notification")

    if data.mentioned_user_ids:
        try:
            brief_row = (
                await db.execute(select(Brief).where(Brief.id == d.brief_id))
            ).scalar_one_or_none()
            await MentionService(db).sync_mentions_for_source(
                agency_id=d.agency_id,
                brand_id=ctx.brand.id,
                brief_id=d.brief_id,
                deliverable_id=d.id,
                source_type="annotation",
                source_id=ann.id,
                actor_user_id=ctx.user.id,
                actor_name=ctx.user.full_name,
                body_text=ann.body or "",
                mentioned_user_ids=data.mentioned_user_ids,
                portal="brand",
                notification_event_type=NotificationEventType.MENTIONED_IN_ANNOTATION.value,
                notification_payload_extra={
                    "brief_id": str(d.brief_id),
                    "brief_title": brief_row.title if brief_row else d.title,
                    "deliverable_id": str(d.id),
                    "deliverable_title": d.title,
                    "annotation_id": str(ann.id),
                    "label_number": ann.label_number,
                    "summary": (
                        f"{ctx.user.full_name} sizi {d.title} üzerindeki bir "
                        f"revizyon notunda etiketledi"
                    ),
                },
            )
            await db.commit()
        except Exception:
            logger.exception("Failed to dispatch brand annotation mention notification")

    return await _brand_annotation_to_read(ann, db)


@brand_portal_router.post(
    "/annotations/{annotation_id}/replies",
    response_model=BrandAnnotationReplyRead,
    status_code=201,
)
async def add_brand_annotation_reply(
    annotation_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    data: BrandAnnotationReplyCreate,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandAnnotationReplyRead:
    from app.models.deliverable_annotation import AnnotationReply, DeliverableAnnotation

    ann_result = await db.execute(
        select(DeliverableAnnotation).where(
            DeliverableAnnotation.id == annotation_id,
            DeliverableAnnotation.deliverable_id == deliverable_id,
            DeliverableAnnotation.brand_id == ctx.brand.id,
            DeliverableAnnotation.visibility == "client_visible",
            DeliverableAnnotation.deleted_at.is_(None),
        )
    )
    ann = ann_result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation bulunamadı")

    reply = AnnotationReply(
        annotation_id=ann.id,
        author_user_id=ctx.user.id,
        author_name=ctx.user.full_name,
        body=data.body.strip(),
        body_html=data.body_html,
        visibility="client_visible",
    )
    db.add(reply)
    await db.commit()
    await db.refresh(reply)

    try:
        from app.models.deliverable import Deliverable
        from app.services.notification_dispatcher import NotificationDispatcher

        deliverable_row = (
            await db.execute(select(Deliverable).where(Deliverable.id == ann.deliverable_id))
        ).scalar_one_or_none()
        dispatcher = NotificationDispatcher(db)
        await dispatcher.emit(
            NotificationEventType.ANNOTATION_REPLIED.value,
            payload={
                "brief_id": str(ann.brief_id),
                "deliverable_id": str(ann.deliverable_id),
                "deliverable_title": deliverable_row.title if deliverable_row else None,
                "annotation_id": str(ann.id),
                "label_number": ann.label_number,
                "brand_name": ctx.brand.name,
                "summary": f"{ctx.brand.name}, #{ann.label_number} numaralı revizyona yanıt verdi",
            },
            agency_id=ann.agency_id,
            brand_id=ctx.brand.id,
            actor_user_id=ctx.user.id,
        )
    except Exception:
        logger.exception("Failed to dispatch annotation.replied notification")

    reply_mentions: list[MentionInline] = []
    if data.mentioned_user_ids:
        try:
            brief_row = (
                await db.execute(select(Brief).where(Brief.id == ann.brief_id))
            ).scalar_one_or_none()
            await MentionService(db).sync_mentions_for_source(
                agency_id=ann.agency_id,
                brand_id=ctx.brand.id,
                brief_id=ann.brief_id,
                deliverable_id=ann.deliverable_id,
                source_type="annotation_reply",
                source_id=reply.id,
                actor_user_id=ctx.user.id,
                actor_name=ctx.user.full_name,
                body_text=reply.body,
                mentioned_user_ids=data.mentioned_user_ids,
                portal="brand",
                notification_event_type=NotificationEventType.MENTIONED_IN_ANNOTATION.value,
                notification_payload_extra={
                    "brief_id": str(ann.brief_id),
                    "brief_title": brief_row.title if brief_row else None,
                    "deliverable_id": str(ann.deliverable_id),
                    "annotation_id": str(ann.id),
                    "label_number": ann.label_number,
                    "summary": f"{ctx.user.full_name} sizi bir revizyon yanıtında etiketledi",
                },
            )
            await db.commit()
            reply_mentions = await MentionService(db).get_inline_mentions(
                source_type="annotation_reply", source_id=reply.id
            )
        except Exception:
            logger.exception("Failed to dispatch brand annotation reply mention notification")

    return BrandAnnotationReplyRead.model_validate(reply).model_copy(
        update={"mentions": reply_mentions}
    )


@brand_portal_router.post(
    "/annotations/{annotation_id}/reopen",
    response_model=BrandAnnotationRead,
)
async def reopen_brand_annotation(
    annotation_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandAnnotationRead:
    """Only a brand manager/owner may reopen a resolved revision — mirrors approve/revise gating."""
    if not ctx.is_manager:
        raise HTTPException(
            status_code=403,
            detail="Yeniden açma yetkisi yalnızca marka yöneticisine aittir",
        )

    from app.models.deliverable import Deliverable
    from app.models.deliverable_annotation import DeliverableAnnotation

    ann_result = await db.execute(
        select(DeliverableAnnotation).where(
            DeliverableAnnotation.id == annotation_id,
            DeliverableAnnotation.deliverable_id == deliverable_id,
            DeliverableAnnotation.brand_id == ctx.brand.id,
            DeliverableAnnotation.visibility == "client_visible",
            DeliverableAnnotation.deleted_at.is_(None),
        )
    )
    ann = ann_result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation bulunamadı")
    if ann.status != "resolved":
        raise HTTPException(status_code=400, detail="Annotation zaten açık")

    ann.status = "open"
    ann.resolved_by_id = None
    ann.resolved_at = None
    await db.commit()
    await db.refresh(ann)

    try:
        from app.models.enums import NotificationEventType
        from app.services.notification_dispatcher import NotificationDispatcher

        deliverable_row = (
            await db.execute(select(Deliverable).where(Deliverable.id == deliverable_id))
        ).scalar_one_or_none()
        dispatcher = NotificationDispatcher(db)
        await dispatcher.emit(
            NotificationEventType.ANNOTATION_REOPENED.value,
            payload={
                "brief_id": str(ann.brief_id),
                "deliverable_id": str(deliverable_id),
                "deliverable_title": deliverable_row.title if deliverable_row else None,
                "annotation_id": str(ann.id),
                "label_number": ann.label_number,
                "brand_name": ctx.brand.name,
                "summary": f"{ctx.brand.name}, #{ann.label_number} numaralı revizyonu yeniden açtı",
            },
            agency_id=ann.agency_id,
            brand_id=ctx.brand.id,
            actor_user_id=ctx.user.id,
        )
    except Exception:
        logger.exception("Failed to dispatch annotation.reopened notification")

    return await _brand_annotation_to_read(ann, db)


# ── Brand mention candidates ───────────────────────────────────────────────────


@brand_portal_router.get(
    "/mentions/candidates",
    response_model=MentionCandidateListResponse,
)
async def list_brand_mention_candidates(
    source_type: str,
    source_id: uuid.UUID | None = None,
    query: str | None = Query(default=None, max_length=100),
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> MentionCandidateListResponse:
    """Brand-side mentionable people: this brand's own active members, plus
    only the agency members assigned to the relevant brief — never the
    agency's full team directory (§C)."""
    if source_type not in {"comment", "annotation", "annotation_reply"}:
        return MentionCandidateListResponse(items=[])

    await rate_limit_mention_candidates(str(ctx.user.id))

    brief_id: uuid.UUID | None = None
    if source_id is not None:
        from app.models.deliverable import Deliverable
        from app.models.deliverable_annotation import AnnotationReply, DeliverableAnnotation

        if source_type == "annotation":
            ann = await db.get(DeliverableAnnotation, source_id)
            if ann and ann.brand_id == ctx.brand.id:
                brief_id = ann.brief_id
        elif source_type == "annotation_reply":
            reply = await db.get(AnnotationReply, source_id)
            if reply is not None:
                parent = await db.get(DeliverableAnnotation, reply.annotation_id)
                if parent and parent.brand_id == ctx.brand.id:
                    brief_id = parent.brief_id
        elif source_type == "comment":
            deliverable = await db.get(Deliverable, source_id)
            if deliverable and deliverable.brand_id == ctx.brand.id:
                brief_id = deliverable.brief_id

    service = MentionService(db)
    candidates = await service.get_brand_candidates(
        brand_id=ctx.brand.id,
        brief_id=brief_id,
        query=query,
        exclude_user_id=ctx.user.id,
    )
    return MentionCandidateListResponse(items=candidates)


# ── Brand onboarding ────────────────────────────────────────────────────────────


def _onboarding_to_read(view: ProgressView) -> OnboardingProgressRead:
    return OnboardingProgressRead(
        id=view.id,
        onboarding_type=view.onboarding_type,
        current_step=view.current_step,
        started_at=view.started_at,
        completed_at=view.completed_at,
        dismissed_at=view.dismissed_at,
        version=view.version,
        percent_complete=view.percent_complete,
        steps=[
            OnboardingStepRead(
                key=s.key,
                completed=s.completed,
                kind=s.kind,
                skipped=s.skipped,
                first_seen_at=s.first_seen_at,
                last_seen_at=s.last_seen_at,
            )
            for s in view.steps
        ],
    )


@brand_portal_router.get("/onboarding/progress", response_model=OnboardingProgressRead)
async def get_brand_onboarding_progress(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressRead:
    onboarding_type = default_onboarding_type_for_brand_role(ctx.membership.role)
    service = OnboardingService(db)
    view = await service.build_progress_view(
        user_id=ctx.user.id, agency_id=None, brand_id=ctx.brand.id, onboarding_type=onboarding_type
    )
    await db.commit()
    return _onboarding_to_read(view)


@brand_portal_router.post("/onboarding/progress/dismiss", response_model=OnboardingProgressRead)
async def dismiss_brand_onboarding(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressRead:
    onboarding_type = default_onboarding_type_for_brand_role(ctx.membership.role)
    service = OnboardingService(db)
    progress = await service.get_or_create_progress(
        user_id=ctx.user.id, agency_id=None, onboarding_type=onboarding_type
    )
    await service.dismiss(progress=progress)
    view = await service.build_progress_view(
        user_id=ctx.user.id, agency_id=None, brand_id=ctx.brand.id, onboarding_type=onboarding_type
    )
    await db.commit()
    return _onboarding_to_read(view)


@brand_portal_router.post("/onboarding/progress/resume", response_model=OnboardingProgressRead)
async def resume_brand_onboarding(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressRead:
    onboarding_type = default_onboarding_type_for_brand_role(ctx.membership.role)
    service = OnboardingService(db)
    progress = await service.get_or_create_progress(
        user_id=ctx.user.id, agency_id=None, onboarding_type=onboarding_type
    )
    await service.resume(progress=progress)
    view = await service.build_progress_view(
        user_id=ctx.user.id, agency_id=None, brand_id=ctx.brand.id, onboarding_type=onboarding_type
    )
    await db.commit()
    return _onboarding_to_read(view)


@brand_portal_router.post(
    "/onboarding/progress/step/{step_key}/seen", response_model=OnboardingProgressRead
)
async def mark_brand_onboarding_step_seen(
    step_key: str,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressRead:
    onboarding_type = default_onboarding_type_for_brand_role(ctx.membership.role)
    service = OnboardingService(db)
    progress = await service.get_or_create_progress(
        user_id=ctx.user.id, agency_id=None, onboarding_type=onboarding_type
    )
    view = await service.build_progress_view(
        user_id=ctx.user.id, agency_id=None, brand_id=ctx.brand.id, onboarding_type=onboarding_type
    )
    if step_key not in {s.key for s in view.steps}:
        raise HTTPException(status_code=404, detail="Bilinmeyen onboarding adımı")
    await service.mark_step_seen(progress=progress, step_key=step_key)
    view = await service.build_progress_view(
        user_id=ctx.user.id, agency_id=None, brand_id=ctx.brand.id, onboarding_type=onboarding_type
    )
    await db.commit()
    return _onboarding_to_read(view)


@brand_portal_router.post(
    "/onboarding/progress/step/{step_key}/skip", response_model=OnboardingProgressRead
)
async def skip_brand_onboarding_step(
    step_key: str,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressRead:
    onboarding_type = default_onboarding_type_for_brand_role(ctx.membership.role)
    service = OnboardingService(db)
    progress = await service.get_or_create_progress(
        user_id=ctx.user.id, agency_id=None, onboarding_type=onboarding_type
    )
    view = await service.build_progress_view(
        user_id=ctx.user.id, agency_id=None, brand_id=ctx.brand.id, onboarding_type=onboarding_type
    )
    if step_key not in {s.key for s in view.steps}:
        raise HTTPException(status_code=404, detail="Bilinmeyen onboarding adımı")
    await service.skip_step(progress=progress, step_key=step_key)
    view = await service.build_progress_view(
        user_id=ctx.user.id, agency_id=None, brand_id=ctx.brand.id, onboarding_type=onboarding_type
    )
    await db.commit()
    return _onboarding_to_read(view)


# ── Brand KPI dashboard ───────────────────────────────────────────────────────


class BrandKPIStats(BaseModel):
    total_briefs: int
    pending_review: int
    revision_requested: int
    approved: int
    in_production: int
    overdue_briefs: int
    pending_deliverables: int
    approved_deliverables: int


@brand_portal_router.get("/dashboard/kpis", response_model=BrandKPIStats)
async def brand_dashboard_kpis(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandKPIStats:
    from sqlalchemy import func

    from app.models.deliverable import Deliverable
    from app.models.enums import BriefStatus

    brand_id = ctx.brand.id
    now = datetime.now(UTC)

    brief_status_counts = await db.execute(
        select(Brief.status, func.count().label("cnt"))
        .where(
            Brief.brand_id == brand_id,
            Brief.deleted_at.is_(None),
        )
        .group_by(Brief.status)
    )
    smap: dict[str, int] = {row.status: row.cnt for row in brief_status_counts}

    overdue = (
        await db.scalar(
            select(func.count())
            .select_from(Brief)
            .where(
                Brief.brand_id == brand_id,
                Brief.deleted_at.is_(None),
                Brief.deadline.isnot(None),
                Brief.deadline < now.date().isoformat(),
                Brief.status.notin_(
                    [
                        BriefStatus.APPROVED.value,
                        BriefStatus.COMPLETED.value,
                        BriefStatus.SCHEDULED.value,
                        BriefStatus.ARCHIVED.value,
                    ]
                ),
            )
        )
        or 0
    )

    deliv_counts = await db.execute(
        select(Deliverable.status, func.count().label("cnt"))
        .where(
            Deliverable.brand_id == brand_id,
            Deliverable.deleted_at.is_(None),
        )
        .group_by(Deliverable.status)
    )
    dmap: dict[str, int] = {row.status: row.cnt for row in deliv_counts}

    return BrandKPIStats(
        total_briefs=sum(smap.values()),
        pending_review=smap.get(BriefStatus.READY_FOR_REVIEW.value, 0),
        revision_requested=smap.get(BriefStatus.REVISION_REQUESTED.value, 0),
        approved=smap.get(BriefStatus.APPROVED.value, 0),
        in_production=smap.get(BriefStatus.IN_PRODUCTION.value, 0),
        overdue_briefs=overdue,
        pending_deliverables=dmap.get("submitted", 0),
        approved_deliverables=dmap.get("approved", 0),
    )


# ── Brand portal: Marka DNA (Identity) endpoints ──────────────────────────────


@brand_portal_router.get("/identity", response_model=BrandIdentityOverview)
async def brand_portal_get_identity(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandIdentityOverview:
    from app.services.brand_identity_service import BrandIdentityService

    svc = BrandIdentityService(db)
    return await svc.get_overview(ctx.brand.id, ctx.brand.agency_id)


@brand_portal_router.post(
    "/identity/documents",
    response_model=BrandIdentityDocumentRead,
    status_code=201,
)
async def brand_portal_upload_identity_document(
    file: UploadFile = File(...),
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandIdentityDocumentRead:
    from app.services.brand_identity_service import BrandIdentityService

    svc = BrandIdentityService(db)
    return await svc.upload_document(ctx.brand.id, ctx.brand.agency_id, file, ctx.user)


@brand_portal_router.get(
    "/identity/documents",
    response_model=list[BrandIdentityDocumentRead],
)
async def brand_portal_list_identity_documents(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[BrandIdentityDocumentRead]:
    from app.services.brand_identity_service import BrandIdentityService

    svc = BrandIdentityService(db)
    return await svc.list_documents(ctx.brand.id, ctx.brand.agency_id)


@brand_portal_router.patch(
    "/identity/profile",
    response_model=BrandIdentityProfileRead,
)
async def brand_portal_update_identity_profile(
    data: BrandIdentityProfileUpdate,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandIdentityProfileRead:
    if not ctx.is_manager:
        raise HTTPException(
            status_code=403,
            detail="Marka DNA düzenleme yetkisi yok (brand_manager veya brand_owner gerekli)",
        )
    from app.services.brand_identity_service import BrandIdentityService

    svc = BrandIdentityService(db)
    return await svc.update_profile(ctx.brand.id, ctx.brand.agency_id, data, ctx.user)


@brand_portal_router.get("/identity/dna-summary", response_model=BrandDNASummary)
async def brand_portal_dna_summary(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandDNASummary:
    from app.services.brand_identity_service import BrandIdentityService

    svc = BrandIdentityService(db)
    return await svc.get_dna_summary(ctx.brand.id)

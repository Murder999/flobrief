"""Agency + Brand KPI dashboard endpoints with real DB aggregation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.core.rbac import Permission
from app.db.session import get_db
from app.models.brand import Brand
from app.models.brand_identity import BrandIdentityProfile
from app.models.brief import Brief
from app.models.brief_task import BriefTask
from app.models.calendar import CalendarItem
from app.models.deliverable import Deliverable
from app.models.enums import BriefStatus

dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_ACTIVE_STATUSES = [
    BriefStatus.DRAFT.value,
    BriefStatus.SUBMITTED.value,
    BriefStatus.ACCEPTED.value,
    BriefStatus.IN_PRODUCTION.value,
    BriefStatus.READY_FOR_REVIEW.value,
    BriefStatus.REVISION_REQUESTED.value,
    BriefStatus.IN_REVIEW.value,
]
_TERMINAL_STATUSES = [
    BriefStatus.APPROVED.value,
    BriefStatus.COMPLETED.value,
    BriefStatus.SCHEDULED.value,
    BriefStatus.ARCHIVED.value,
]


# ── Agency KPI schemas ────────────────────────────────────────────────────────


class AgencyKPIStats(BaseModel):
    pending_briefs: int
    accepted_briefs: int
    in_production_briefs: int
    pending_deliverables: int
    revision_requested_deliverables: int
    overdue_briefs: int
    completed_this_month: int
    approved_this_month: int
    open_tasks: int
    overdue_tasks: int
    total_deliverables_submitted: int
    total_deliverables_approved: int


class WorkloadMember(BaseModel):
    user_id: uuid.UUID
    full_name: str | None
    open_tasks: int
    overdue_tasks: int


class AgencyWorkloadStats(BaseModel):
    members: list[WorkloadMember]


# ── Brief Center schemas ──────────────────────────────────────────────────────


class BriefCenterKPI(BaseModel):
    total_active_briefs: int
    overdue_briefs: int
    revision_requested: int
    pending_approvals: int
    new_brand_requests: int
    due_today: int


class AttentionItem(BaseModel):
    id: uuid.UUID
    title: str
    brand_id: uuid.UUID | None
    brand_name: str | None
    status: str
    priority: str
    deadline: str | None
    days_overdue: int | None
    source: str | None
    attention_reason: str


class BrandCardItem(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    status: str
    active_brief_count: int
    overdue_count: int
    revision_requested_count: int
    pending_approval_count: int
    this_week_calendar_count: int
    last_activity_at: str | None
    has_brand_dna: bool
    brand_dna_status: str | None


class BriefCenterResponse(BaseModel):
    kpis: BriefCenterKPI
    attention_items: list[AttentionItem]
    brand_cards: list[BrandCardItem]


# ── Brand Workspace schemas ───────────────────────────────────────────────────


class BrandKPI(BaseModel):
    active_briefs: int
    overdue_briefs: int
    revision_requested: int
    pending_approvals: int
    this_week_calendar: int


class BrandBriefSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    priority: str
    deadline: str | None
    source: str | None
    updated_at: str


class BrandDeliverableSummary(BaseModel):
    id: uuid.UUID
    brief_id: uuid.UUID
    title: str
    deliverable_type: str
    status: str
    version_number: int
    revision_count: int
    updated_at: str


class BrandCalendarItemSummary(BaseModel):
    id: uuid.UUID
    title: str
    item_type: str
    platform: str
    status: str
    publish_at: str | None
    due_at: str | None
    brief_id: uuid.UUID | None


class BrandDNASummary(BaseModel):
    has_profile: bool
    status: str | None
    primary_colors: list | None
    typography: list | None
    tone_of_voice: dict | None
    summary: str | None


class BrandWorkspaceResponse(BaseModel):
    brand_id: uuid.UUID
    brand_name: str
    brand_logo_url: str | None
    brand_status: str
    kpis: BrandKPI
    recent_briefs: list[BrandBriefSummary]
    recent_deliverables: list[BrandDeliverableSummary]
    upcoming_calendar: list[BrandCalendarItemSummary]
    brand_dna: BrandDNASummary


# ── Agency KPI endpoint ───────────────────────────────────────────────────────


@dashboard_router.get("/agency-kpis", response_model=AgencyKPIStats)
async def agency_kpis(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> AgencyKPIStats:
    if not workspace.has_permission(Permission.AGENCY_VIEW):
        raise HTTPException(status_code=403, detail="Yetersiz yetki")

    agency_id = workspace.agency.id
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    brief_status_counts = await db.execute(
        select(Brief.status, func.count().label("cnt"))
        .where(Brief.agency_id == agency_id, Brief.deleted_at.is_(None))
        .group_by(Brief.status)
    )
    status_map: dict[str, int] = {row.status: row.cnt for row in brief_status_counts}

    overdue_briefs = (
        await db.scalar(
            select(func.count())
            .select_from(Brief)
            .where(
                Brief.agency_id == agency_id,
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

    completed_this_month = (
        await db.scalar(
            select(func.count())
            .select_from(Brief)
            .where(
                Brief.agency_id == agency_id,
                Brief.deleted_at.is_(None),
                Brief.updated_at >= month_start,
                Brief.status.in_([BriefStatus.COMPLETED.value, BriefStatus.SCHEDULED.value]),
            )
        )
        or 0
    )

    approved_this_month = (
        await db.scalar(
            select(func.count())
            .select_from(Brief)
            .where(
                Brief.agency_id == agency_id,
                Brief.deleted_at.is_(None),
                Brief.updated_at >= month_start,
                Brief.status == BriefStatus.APPROVED.value,
            )
        )
        or 0
    )

    deliverable_status_counts = await db.execute(
        select(Deliverable.status, func.count().label("cnt"))
        .where(
            Deliverable.agency_id == agency_id,
            Deliverable.deleted_at.is_(None),
        )
        .group_by(Deliverable.status)
    )
    deliv_map: dict[str, int] = {row.status: row.cnt for row in deliverable_status_counts}

    open_tasks = (
        await db.scalar(
            select(func.count())
            .select_from(BriefTask)
            .where(
                BriefTask.agency_id == agency_id,
                BriefTask.deleted_at.is_(None),
                BriefTask.status.in_(["todo", "in_progress", "blocked"]),
            )
        )
        or 0
    )

    overdue_tasks = (
        await db.scalar(
            select(func.count())
            .select_from(BriefTask)
            .where(
                BriefTask.agency_id == agency_id,
                BriefTask.deleted_at.is_(None),
                BriefTask.due_date.isnot(None),
                BriefTask.due_date < now.date(),
                BriefTask.status.notin_(["done"]),
            )
        )
        or 0
    )

    return AgencyKPIStats(
        pending_briefs=status_map.get(BriefStatus.SUBMITTED.value, 0),
        accepted_briefs=status_map.get(BriefStatus.ACCEPTED.value, 0),
        in_production_briefs=status_map.get(BriefStatus.IN_PRODUCTION.value, 0),
        pending_deliverables=deliv_map.get("submitted", 0),
        revision_requested_deliverables=deliv_map.get("revision_requested", 0),
        overdue_briefs=overdue_briefs,
        completed_this_month=completed_this_month,
        approved_this_month=approved_this_month,
        open_tasks=open_tasks,
        overdue_tasks=overdue_tasks,
        total_deliverables_submitted=deliv_map.get("submitted", 0) + deliv_map.get("approved", 0),
        total_deliverables_approved=deliv_map.get("approved", 0),
    )


@dashboard_router.get("/workload", response_model=AgencyWorkloadStats)
async def agency_workload(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> AgencyWorkloadStats:
    if not workspace.has_permission(Permission.AGENCY_VIEW):
        raise HTTPException(status_code=403, detail="Yetersiz yetki")

    agency_id = workspace.agency.id
    now = datetime.now(UTC)

    from app.models.user import User

    rows = await db.execute(
        select(
            User.id,
            User.full_name,
            func.count(
                case(
                    (BriefTask.status.in_(["todo", "in_progress", "blocked"]), 1),
                )
            ).label("open_tasks"),
            func.count(
                case(
                    (
                        and_(
                            BriefTask.due_date.isnot(None),
                            BriefTask.due_date < now.date(),
                            BriefTask.status.notin_(["done"]),
                        ),
                        1,
                    ),
                )
            ).label("overdue_tasks"),
        )
        .outerjoin(
            BriefTask,
            and_(
                BriefTask.assigned_to_id == User.id,
                BriefTask.agency_id == agency_id,
                BriefTask.deleted_at.is_(None),
            ),
        )
        .join(
            __import__("app.models.agency_member", fromlist=["AgencyMember"]).AgencyMember,
            and_(
                __import__(
                    "app.models.agency_member", fromlist=["AgencyMember"]
                ).AgencyMember.user_id
                == User.id,
                __import__(
                    "app.models.agency_member", fromlist=["AgencyMember"]
                ).AgencyMember.agency_id
                == agency_id,
                __import__(
                    "app.models.agency_member", fromlist=["AgencyMember"]
                ).AgencyMember.deleted_at.is_(None),
            ),
        )
        .where(User.deleted_at.is_(None), User.is_active.is_(True))
        .group_by(User.id, User.full_name)
        .order_by(func.count(BriefTask.id).desc())
    )

    members = [
        WorkloadMember(
            user_id=row.id,
            full_name=row.full_name,
            open_tasks=row.open_tasks or 0,
            overdue_tasks=row.overdue_tasks or 0,
        )
        for row in rows
    ]
    return AgencyWorkloadStats(members=members)


# ── Brief Center endpoint ─────────────────────────────────────────────────────


@dashboard_router.get("/brief-center", response_model=BriefCenterResponse)
async def brief_center(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> BriefCenterResponse:
    if not workspace.has_permission(Permission.AGENCY_VIEW):
        raise HTTPException(status_code=403, detail="Yetersiz yetki")

    agency_id = workspace.agency.id
    now = datetime.now(UTC)
    today_str = str(now.date())
    week_end = now + timedelta(days=7)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_active = (
        await db.scalar(
            select(func.count())
            .select_from(Brief)
            .where(
                Brief.agency_id == agency_id,
                Brief.deleted_at.is_(None),
                Brief.status.in_(_ACTIVE_STATUSES),
            )
        )
        or 0
    )

    overdue_count = (
        await db.scalar(
            select(func.count())
            .select_from(Brief)
            .where(
                Brief.agency_id == agency_id,
                Brief.deleted_at.is_(None),
                Brief.deadline.isnot(None),
                Brief.deadline < today_str,
                Brief.status.notin_(_TERMINAL_STATUSES),
            )
        )
        or 0
    )

    revision_count = (
        await db.scalar(
            select(func.count())
            .select_from(Brief)
            .where(
                Brief.agency_id == agency_id,
                Brief.deleted_at.is_(None),
                Brief.status == BriefStatus.REVISION_REQUESTED.value,
            )
        )
        or 0
    )

    pending_approvals = (
        await db.scalar(
            select(func.count())
            .select_from(Deliverable)
            .where(
                Deliverable.agency_id == agency_id,
                Deliverable.deleted_at.is_(None),
                Deliverable.status == "submitted",
            )
        )
        or 0
    )

    new_brand_requests = (
        await db.scalar(
            select(func.count())
            .select_from(Brief)
            .where(
                Brief.agency_id == agency_id,
                Brief.deleted_at.is_(None),
                Brief.source == "brand_portal",
                Brief.status == BriefStatus.SUBMITTED.value,
            )
        )
        or 0
    )

    due_today = (
        await db.scalar(
            select(func.count())
            .select_from(Brief)
            .where(
                Brief.agency_id == agency_id,
                Brief.deleted_at.is_(None),
                Brief.deadline == today_str,
                Brief.status.notin_(_TERMINAL_STATUSES),
            )
        )
        or 0
    )

    kpis = BriefCenterKPI(
        total_active_briefs=total_active,
        overdue_briefs=overdue_count,
        revision_requested=revision_count,
        pending_approvals=pending_approvals,
        new_brand_requests=new_brand_requests,
        due_today=due_today,
    )

    # ── Attention Items ────────────────────────────────────────────────────────
    attention_rows = await db.execute(
        select(Brief, Brand.name.label("brand_name"))
        .outerjoin(Brand, and_(Brief.brand_id == Brand.id, Brand.deleted_at.is_(None)))
        .where(
            Brief.agency_id == agency_id,
            Brief.deleted_at.is_(None),
            Brief.status.notin_(_TERMINAL_STATUSES),
            or_(
                and_(Brief.deadline.isnot(None), Brief.deadline < today_str),
                Brief.status == BriefStatus.REVISION_REQUESTED.value,
                Brief.priority == "urgent",
                and_(Brief.source == "brand_portal", Brief.status == BriefStatus.SUBMITTED.value),
            ),
        )
        .order_by(Brief.deadline.asc().nulls_last(), Brief.updated_at.desc())
        .limit(25)
    )

    attention_items: list[AttentionItem] = []
    for brief, brand_name in attention_rows:
        days_overdue: int | None = None
        if brief.deadline and brief.deadline < today_str:
            from datetime import date as date_type

            deadline_date = date_type.fromisoformat(brief.deadline)
            days_overdue = (now.date() - deadline_date).days

        if brief.deadline and brief.deadline < today_str:
            reason = "overdue"
        elif brief.status == BriefStatus.REVISION_REQUESTED.value:
            reason = "revision_requested"
        elif brief.source == "brand_portal" and brief.status == BriefStatus.SUBMITTED.value:
            reason = "new_request"
        else:
            reason = "urgent"

        attention_items.append(
            AttentionItem(
                id=brief.id,
                title=brief.title,
                brand_id=brief.brand_id,
                brand_name=brand_name,
                status=brief.status,
                priority=brief.priority,
                deadline=brief.deadline,
                days_overdue=days_overdue,
                source=brief.source,
                attention_reason=reason,
            )
        )

    # ── Brand Cards ───────────────────────────────────────────────────────────
    brands_result = await db.execute(
        select(Brand)
        .where(
            Brand.agency_id == agency_id,
            Brand.deleted_at.is_(None),
            Brand.status.notin_(["deleted"]),
        )
        .order_by(Brand.name)
    )
    brands_list = list(brands_result.scalars())

    brand_cards: list[BrandCardItem] = []
    if brands_list:
        brand_ids = [b.id for b in brands_list]

        # Brief aggregates per brand
        brief_agg_rows = await db.execute(
            select(
                Brief.brand_id,
                func.count(case((Brief.status.in_(_ACTIVE_STATUSES), 1))).label("active"),
                func.count(
                    case(
                        (
                            and_(
                                Brief.deadline.isnot(None),
                                Brief.deadline < today_str,
                                Brief.status.notin_(_TERMINAL_STATUSES),
                            ),
                            1,
                        )
                    )
                ).label("overdue"),
                func.count(case((Brief.status == BriefStatus.REVISION_REQUESTED.value, 1))).label(
                    "revision"
                ),
                func.max(Brief.updated_at).label("last_activity"),
            )
            .where(
                Brief.agency_id == agency_id,
                Brief.brand_id.in_(brand_ids),
                Brief.deleted_at.is_(None),
            )
            .group_by(Brief.brand_id)
        )
        brief_map: dict[uuid.UUID, dict] = {}
        for row in brief_agg_rows:
            brief_map[row.brand_id] = {
                "active": row.active or 0,
                "overdue": row.overdue or 0,
                "revision": row.revision or 0,
                "last_activity": row.last_activity,
            }

        # Pending deliverable approvals per brand
        deliv_agg_rows = await db.execute(
            select(Deliverable.brand_id, func.count().label("pending"))
            .where(
                Deliverable.agency_id == agency_id,
                Deliverable.brand_id.in_(brand_ids),
                Deliverable.deleted_at.is_(None),
                Deliverable.status == "submitted",
            )
            .group_by(Deliverable.brand_id)
        )
        deliv_map: dict[uuid.UUID, int] = {row.brand_id: row.pending for row in deliv_agg_rows}

        # This week calendar items per brand
        cal_agg_rows = await db.execute(
            select(CalendarItem.brand_id, func.count().label("this_week"))
            .where(
                CalendarItem.agency_id == agency_id,
                CalendarItem.brand_id.in_(brand_ids),
                CalendarItem.deleted_at.is_(None),
                or_(
                    and_(CalendarItem.publish_at >= now, CalendarItem.publish_at <= week_end),
                    and_(CalendarItem.due_at >= now, CalendarItem.due_at <= week_end),
                ),
            )
            .group_by(CalendarItem.brand_id)
        )
        cal_map: dict[uuid.UUID, int] = {row.brand_id: row.this_week for row in cal_agg_rows}

        # Brand DNA status per brand
        dna_rows = await db.execute(
            select(BrandIdentityProfile.brand_id, BrandIdentityProfile.status).where(
                BrandIdentityProfile.brand_id.in_(brand_ids),
                BrandIdentityProfile.is_active.is_(True),
                BrandIdentityProfile.deleted_at.is_(None),
            )
        )
        dna_map: dict[uuid.UUID, str] = {row.brand_id: row.status for row in dna_rows}

        for brand in brands_list:
            brief_data = brief_map.get(brand.id, {})
            last_activity = brief_data.get("last_activity")
            brand_cards.append(
                BrandCardItem(
                    id=brand.id,
                    name=brand.name,
                    logo_url=brand.logo_url,
                    status=brand.status,
                    active_brief_count=brief_data.get("active", 0),
                    overdue_count=brief_data.get("overdue", 0),
                    revision_requested_count=brief_data.get("revision", 0),
                    pending_approval_count=deliv_map.get(brand.id, 0),
                    this_week_calendar_count=cal_map.get(brand.id, 0),
                    last_activity_at=last_activity.isoformat() if last_activity else None,
                    has_brand_dna=brand.id in dna_map,
                    brand_dna_status=dna_map.get(brand.id),
                )
            )

    return BriefCenterResponse(
        kpis=kpis,
        attention_items=attention_items,
        brand_cards=brand_cards,
    )


# ── Brand Workspace endpoint ──────────────────────────────────────────────────


@dashboard_router.get("/brands/{brand_id}/workspace", response_model=BrandWorkspaceResponse)
async def brand_workspace(
    brand_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> BrandWorkspaceResponse:
    if not workspace.has_permission(Permission.AGENCY_VIEW):
        raise HTTPException(status_code=403, detail="Yetersiz yetki")

    agency_id = workspace.agency.id
    now = datetime.now(UTC)
    today_str = str(now.date())
    week_end = now + timedelta(days=7)

    brand = await db.scalar(
        select(Brand).where(
            Brand.id == brand_id,
            Brand.agency_id == agency_id,
            Brand.deleted_at.is_(None),
        )
    )
    if not brand:
        raise HTTPException(status_code=404, detail="Marka bulunamadı")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    active_briefs = (
        await db.scalar(
            select(func.count())
            .select_from(Brief)
            .where(
                Brief.agency_id == agency_id,
                Brief.brand_id == brand_id,
                Brief.deleted_at.is_(None),
                Brief.status.in_(_ACTIVE_STATUSES),
            )
        )
        or 0
    )

    overdue_briefs = (
        await db.scalar(
            select(func.count())
            .select_from(Brief)
            .where(
                Brief.agency_id == agency_id,
                Brief.brand_id == brand_id,
                Brief.deleted_at.is_(None),
                Brief.deadline.isnot(None),
                Brief.deadline < today_str,
                Brief.status.notin_(_TERMINAL_STATUSES),
            )
        )
        or 0
    )

    revision_requested = (
        await db.scalar(
            select(func.count())
            .select_from(Brief)
            .where(
                Brief.agency_id == agency_id,
                Brief.brand_id == brand_id,
                Brief.deleted_at.is_(None),
                Brief.status == BriefStatus.REVISION_REQUESTED.value,
            )
        )
        or 0
    )

    pending_approvals = (
        await db.scalar(
            select(func.count())
            .select_from(Deliverable)
            .where(
                Deliverable.agency_id == agency_id,
                Deliverable.brand_id == brand_id,
                Deliverable.deleted_at.is_(None),
                Deliverable.status == "submitted",
            )
        )
        or 0
    )

    this_week_calendar = (
        await db.scalar(
            select(func.count())
            .select_from(CalendarItem)
            .where(
                CalendarItem.agency_id == agency_id,
                CalendarItem.brand_id == brand_id,
                CalendarItem.deleted_at.is_(None),
                or_(
                    and_(CalendarItem.publish_at >= now, CalendarItem.publish_at <= week_end),
                    and_(CalendarItem.due_at >= now, CalendarItem.due_at <= week_end),
                ),
            )
        )
        or 0
    )

    # ── Recent Briefs ─────────────────────────────────────────────────────────
    recent_briefs_result = await db.execute(
        select(Brief)
        .where(
            Brief.agency_id == agency_id,
            Brief.brand_id == brand_id,
            Brief.deleted_at.is_(None),
        )
        .order_by(Brief.updated_at.desc())
        .limit(20)
    )
    recent_briefs = [
        BrandBriefSummary(
            id=b.id,
            title=b.title,
            status=b.status,
            priority=b.priority,
            deadline=b.deadline,
            source=b.source,
            updated_at=b.updated_at.isoformat(),
        )
        for b in recent_briefs_result.scalars()
    ]

    # ── Recent Deliverables ───────────────────────────────────────────────────
    recent_deliverables_result = await db.execute(
        select(Deliverable)
        .where(
            Deliverable.agency_id == agency_id,
            Deliverable.brand_id == brand_id,
            Deliverable.deleted_at.is_(None),
        )
        .order_by(Deliverable.updated_at.desc())
        .limit(20)
    )
    recent_deliverables = [
        BrandDeliverableSummary(
            id=d.id,
            brief_id=d.brief_id,
            title=d.title,
            deliverable_type=d.deliverable_type,
            status=d.status,
            version_number=d.version_number,
            revision_count=d.revision_count,
            updated_at=d.updated_at.isoformat(),
        )
        for d in recent_deliverables_result.scalars()
    ]

    # ── Upcoming Calendar Items ───────────────────────────────────────────────
    upcoming_cal_result = await db.execute(
        select(CalendarItem)
        .where(
            CalendarItem.agency_id == agency_id,
            CalendarItem.brand_id == brand_id,
            CalendarItem.deleted_at.is_(None),
            or_(
                CalendarItem.publish_at >= now,
                and_(CalendarItem.due_at >= now, CalendarItem.publish_at.is_(None)),
            ),
        )
        .order_by(func.coalesce(CalendarItem.publish_at, CalendarItem.due_at).asc())
        .limit(20)
    )
    upcoming_calendar = [
        BrandCalendarItemSummary(
            id=c.id,
            title=c.title,
            item_type=c.item_type,
            platform=c.platform,
            status=c.status,
            publish_at=c.publish_at.isoformat() if c.publish_at else None,
            due_at=c.due_at.isoformat() if c.due_at else None,
            brief_id=c.brief_id,
        )
        for c in upcoming_cal_result.scalars()
    ]

    # ── Brand DNA ─────────────────────────────────────────────────────────────
    dna_profile = await db.scalar(
        select(BrandIdentityProfile)
        .where(
            BrandIdentityProfile.brand_id == brand_id,
            BrandIdentityProfile.is_active.is_(True),
            BrandIdentityProfile.deleted_at.is_(None),
        )
        .order_by(BrandIdentityProfile.created_at.desc())
        .limit(1)
    )

    brand_dna = BrandDNASummary(
        has_profile=dna_profile is not None,
        status=dna_profile.status if dna_profile else None,
        primary_colors=dna_profile.primary_colors if dna_profile else None,
        typography=dna_profile.typography if dna_profile else None,
        tone_of_voice=dna_profile.tone_of_voice if dna_profile else None,
        summary=dna_profile.summary if dna_profile else None,
    )

    return BrandWorkspaceResponse(
        brand_id=brand.id,
        brand_name=brand.name,
        brand_logo_url=brand.logo_url,
        brand_status=brand.status,
        kpis=BrandKPI(
            active_briefs=active_briefs,
            overdue_briefs=overdue_briefs,
            revision_requested=revision_requested,
            pending_approvals=pending_approvals,
            this_week_calendar=this_week_calendar,
        ),
        recent_briefs=recent_briefs,
        recent_deliverables=recent_deliverables,
        upcoming_calendar=upcoming_calendar,
        brand_dna=brand_dna,
    )

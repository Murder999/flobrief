"""Finance + capacity background scheduler (Part 2, Phase 7 — plan §14).

Structurally mirrors `time_tracking_scheduler.py`: one fresh session per
run, one independently-exception-isolated check per concern, hourly loop,
dedupe via a JSONB-payload lookup on `NotificationEvent` before emitting.
Covers the Phase-7 + Part 6B-1 events that are naturally scan-based rather
than triggered by a single user action:

- CAPACITY_OVER_THRESHOLD — a team member's actual utilization for the
  current week has crossed the agency's "overloaded" threshold.
- COMMERCIAL_TERMS_EXPIRING — an active CommercialTerms row's `valid_until`
  falls within the lookahead window.
- INVOICE_OVERDUE — a sent/partially-paid ClientInvoice's `due_date` has
  passed.
- INVOICE_DUE_SOON — a sent ClientInvoice's `due_date` falls within the
  lookahead window and hasn't passed yet.
- CRITICAL_WORK_UNASSIGNED — a brief/task with no assignee has a deadline
  inside the lookahead window (mirrors `deadline_scheduler`'s lookahead).

No emission here ever mutates a Brief/CommercialTerms/ClientInvoice/
WorkAllocation row — this module only reads existing rows and dispatches
notifications, same contract as `time_tracking_scheduler.py`."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission, get_permissions_for_agency_role
from app.core.time_utils import utc_today
from app.db.session import AsyncSessionLocal
from app.models.agency_member import AgencyMember
from app.models.brief import Brief
from app.models.client_invoice import ClientInvoice
from app.models.commercial_terms import CommercialTerms
from app.models.enums import (
    AgencyMemberStatus,
    ClientInvoiceStatus,
    NotificationEventType,
)
from app.models.notification import NotificationEvent
from app.services.capacity_calculation_service import CapacityCalculationService
from app.services.notification_dispatcher import NotificationDispatcher

log = logging.getLogger(__name__)

_DEDUP_HOURS = 23  # mirrors time_tracking_scheduler / deadline_scheduler
_TERMS_EXPIRY_LOOKAHEAD_DAYS = 14
_CRITICAL_WORK_LOOKAHEAD_DAYS = 3  # mirrors deadline_scheduler._LOOKAHEAD_DAYS
_INVOICE_DUE_SOON_LOOKAHEAD_DAYS = 3  # mirrors deadline_scheduler._LOOKAHEAD_DAYS


async def _already_notified(
    db: AsyncSession, event_type: str, entity_key: str, entity_value: str
) -> bool:
    cutoff = datetime.now(UTC) - timedelta(hours=_DEDUP_HOURS)
    stmt = (
        select(NotificationEvent.id)
        .where(
            NotificationEvent.event_type == event_type,
            NotificationEvent.created_at >= cutoff,
            func.jsonb_extract_path_text(cast(NotificationEvent.payload, JSONB), entity_key)
            == entity_value,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _active_agency_ids(db: AsyncSession) -> list[uuid.UUID]:
    rows = await db.execute(
        select(AgencyMember.agency_id).where(AgencyMember.deleted_at.is_(None)).distinct()
    )
    return [row[0] for row in rows]


async def _recipients_with_permission(
    db: AsyncSession, agency_id: uuid.UUID, permission: Permission
) -> list[uuid.UUID]:
    rows = await db.execute(
        select(AgencyMember.user_id, AgencyMember.role).where(
            AgencyMember.agency_id == agency_id,
            AgencyMember.deleted_at.is_(None),
            AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
        )
    )
    return [row.user_id for row in rows if permission in get_permissions_for_agency_role(row.role)]


async def _check_capacity_over_threshold(db: AsyncSession) -> None:
    """A team member whose actual utilization for the current ISO week has
    reached the agency's "overloaded" threshold (plan §6, `_status_for_pct`
    returning "overloaded"). Notifies the member themselves plus anyone who
    can view team capacity — never includes cost/rate figures, only a
    utilization percentage."""
    today = utc_today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    dispatcher = NotificationDispatcher(db)
    for agency_id in await _active_agency_ids(db):
        try:
            report = await CapacityCalculationService(db).team_capacity(
                agency_id, week_start, week_end
            )
        except Exception:
            log.exception("Failed to compute team_capacity for agency %s", agency_id)
            continue

        overloaded = [m for m in report.members if m.actual_status == "overloaded"]
        if not overloaded:
            continue

        manager_ids = await _recipients_with_permission(
            db, agency_id, Permission.CAPACITY_VIEW_TEAM
        )

        for member in overloaded:
            dedup_key = f"{agency_id}:{member.user_id}:{week_start.isoformat()}"
            if await _already_notified(
                db, NotificationEventType.CAPACITY_OVER_THRESHOLD.value, "dedup_key", dedup_key
            ):
                continue
            recipient_ids = list({member.user_id, *manager_ids})
            try:
                await dispatcher.emit(
                    NotificationEventType.CAPACITY_OVER_THRESHOLD.value,
                    payload={
                        "dedup_key": dedup_key,
                        "user_id": str(member.user_id),
                        "week_start": week_start.isoformat(),
                        "week_end": week_end.isoformat(),
                        "actual_utilization_pct": member.actual_utilization_pct,
                        "summary": (
                            f"{member.user_name} bu hafta kapasitenin "
                            f"%{member.actual_utilization_pct} kadarında çalışıyor."
                        ),
                    },
                    agency_id=agency_id,
                    brand_id=None,
                    actor_user_id=None,
                    recipient_ids=recipient_ids,
                )
                await db.commit()
            except Exception:
                await db.rollback()
                log.exception(
                    "Failed to send CAPACITY_OVER_THRESHOLD for user %s agency %s",
                    member.user_id,
                    agency_id,
                )


async def _check_commercial_terms_expiring(db: AsyncSession) -> None:
    """Active CommercialTerms whose `valid_until` falls within the lookahead
    window. Notifies whoever can manage commercial terms — payload carries
    only the billing model and dates, never rate/tax figures."""
    today = utc_today()
    window_end = today + timedelta(days=_TERMS_EXPIRY_LOOKAHEAD_DAYS)

    result = await db.execute(
        select(CommercialTerms).where(
            CommercialTerms.active.is_(True),
            CommercialTerms.deleted_at.is_(None),
            CommercialTerms.valid_until.is_not(None),
            CommercialTerms.valid_until >= today,
            CommercialTerms.valid_until <= window_end,
        )
    )
    terms_rows = list(result.scalars().all())
    if not terms_rows:
        return

    dispatcher = NotificationDispatcher(db)
    for terms in terms_rows:
        dedup_key = f"{terms.id}:{terms.valid_until.isoformat()}"
        if await _already_notified(
            db, NotificationEventType.COMMERCIAL_TERMS_EXPIRING.value, "dedup_key", dedup_key
        ):
            continue

        recipient_ids = await _recipients_with_permission(
            db, terms.agency_id, Permission.COMMERCIAL_TERMS_MANAGE
        )
        if not recipient_ids:
            continue

        days_left = (terms.valid_until - today).days
        try:
            await dispatcher.emit(
                NotificationEventType.COMMERCIAL_TERMS_EXPIRING.value,
                payload={
                    "dedup_key": dedup_key,
                    "commercial_terms_id": str(terms.id),
                    "billing_model": terms.billing_model,
                    "valid_until": terms.valid_until.isoformat(),
                    "summary": (f"Bir markanın ticari koşulu {days_left} gün içinde sona eriyor."),
                },
                agency_id=terms.agency_id,
                brand_id=terms.brand_id,
                actor_user_id=None,
                recipient_ids=recipient_ids,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception("Failed to send COMMERCIAL_TERMS_EXPIRING for terms %s", terms.id)


async def _check_invoice_overdue(db: AsyncSession) -> None:
    """Sent/partially-paid ClientInvoice rows whose `due_date` has passed.
    Re-fires daily (23h dedupe window) until the invoice is paid/voided —
    same "keep reminding until resolved" shape as CALENDAR_ITEM_DUE. Notifies
    whoever can approve invoices (the actionable, agency-side audience) —
    never the brand. Payload carries no monetary figures, only identifiers/
    dates, to stay unambiguously clear of the "no cost/rate figures" rule."""
    today = utc_today()
    result = await db.execute(
        select(ClientInvoice).where(
            ClientInvoice.deleted_at.is_(None),
            ClientInvoice.status.in_(
                [ClientInvoiceStatus.SENT.value, ClientInvoiceStatus.PARTIALLY_PAID.value]
            ),
            ClientInvoice.due_date < today,
        )
    )
    overdue_invoices = list(result.scalars().all())
    if not overdue_invoices:
        return

    dispatcher = NotificationDispatcher(db)
    for invoice in overdue_invoices:
        entry_id_str = str(invoice.id)
        if await _already_notified(
            db, NotificationEventType.INVOICE_OVERDUE.value, "invoice_id", entry_id_str
        ):
            continue

        recipient_ids = await _recipients_with_permission(
            db, invoice.agency_id, Permission.INVOICE_APPROVE
        )
        if not recipient_ids:
            continue

        days_overdue = (today - invoice.due_date).days
        try:
            await dispatcher.emit(
                NotificationEventType.INVOICE_OVERDUE.value,
                payload={
                    "invoice_id": entry_id_str,
                    "invoice_number": invoice.invoice_number,
                    "due_date": invoice.due_date.isoformat(),
                    "days_overdue": days_overdue,
                    "summary": (
                        f"{invoice.invoice_number} numaralı fatura {days_overdue} "
                        "gündür vadesi geçmiş durumda."
                    ),
                },
                agency_id=invoice.agency_id,
                brand_id=invoice.brand_id,
                actor_user_id=None,
                recipient_ids=recipient_ids,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception("Failed to send INVOICE_OVERDUE for invoice %s", invoice.id)


async def _check_invoice_due_soon(db: AsyncSession) -> None:
    """Sent ClientInvoice rows whose `due_date` falls within the lookahead
    window and hasn't passed yet (that's `_check_invoice_overdue`'s job —
    the two are mutually exclusive by the `due_date >= today` / `< today`
    split, so an invoice never fires both on the same day). Notifies the
    brand's own users (the client who owes the payment), same audience as
    INVOICE_SENT — never agency staff. Payload carries no monetary figures,
    same rule as INVOICE_OVERDUE."""
    today = utc_today()
    window_end = today + timedelta(days=_INVOICE_DUE_SOON_LOOKAHEAD_DAYS)
    result = await db.execute(
        select(ClientInvoice).where(
            ClientInvoice.deleted_at.is_(None),
            ClientInvoice.status == ClientInvoiceStatus.SENT.value,
            ClientInvoice.due_date >= today,
            ClientInvoice.due_date <= window_end,
        )
    )
    due_soon_invoices = list(result.scalars().all())
    if not due_soon_invoices:
        return

    dispatcher = NotificationDispatcher(db)
    for invoice in due_soon_invoices:
        entry_id_str = str(invoice.id)
        if await _already_notified(
            db, NotificationEventType.INVOICE_DUE_SOON.value, "invoice_id", entry_id_str
        ):
            continue

        brand_recipients = await dispatcher.get_brand_members(invoice.brand_id)
        if not brand_recipients:
            continue

        days_left = (invoice.due_date - today).days
        try:
            await dispatcher.emit(
                NotificationEventType.INVOICE_DUE_SOON.value,
                payload={
                    "invoice_id": entry_id_str,
                    "invoice_number": invoice.invoice_number,
                    "due_date": invoice.due_date.isoformat(),
                    "days_left": days_left,
                    "summary": (
                        f"{invoice.invoice_number} numaralı faturanın vadesine "
                        f"{days_left} gün kaldı."
                    ),
                },
                agency_id=invoice.agency_id,
                brand_id=invoice.brand_id,
                actor_user_id=None,
                recipient_ids=[u.id for u in brand_recipients],
            )
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception("Failed to send INVOICE_DUE_SOON for invoice %s", invoice.id)


async def _check_critical_work_unassigned(db: AsyncSession) -> None:
    """Unassigned brief/task work (plan §9 `CapacityCalculationService.
    unassigned_work`) whose brief has a deadline inside the lookahead
    window — the same "about to be late and nobody owns it" risk
    `deadline_scheduler` flags for assigned briefs, extended to the
    unassigned case. Notifies whoever can manage allocations (the audience
    that can actually assign someone)."""
    today = utc_today()
    window_end = (today + timedelta(days=_CRITICAL_WORK_LOOKAHEAD_DAYS)).isoformat()
    window_start = today.isoformat()

    dispatcher = NotificationDispatcher(db)
    for agency_id in await _active_agency_ids(db):
        try:
            report = await CapacityCalculationService(db).unassigned_work(agency_id, today, today)
        except Exception:
            log.exception("Failed to compute unassigned_work for agency %s", agency_id)
            continue
        if not report.items:
            continue

        brief_ids = {item.brief_id for item in report.items}
        brief_rows = await db.execute(
            select(Brief.id, Brief.title, Brief.deadline).where(
                Brief.id.in_(brief_ids),
                Brief.deadline.is_not(None),
                Brief.deadline >= window_start,
                Brief.deadline <= window_end,
            )
        )
        urgent_briefs = {row.id: (row.title, row.deadline) for row in brief_rows}
        if not urgent_briefs:
            continue

        recipient_ids = await _recipients_with_permission(
            db, agency_id, Permission.CAPACITY_MANAGE_ALLOCATION
        )
        if not recipient_ids:
            continue

        for item in report.items:
            if item.brief_id not in urgent_briefs:
                continue
            brief_title, deadline = urgent_briefs[item.brief_id]
            dedup_key = f"{item.brief_id}:{item.task_id or 'brief'}:{deadline}"
            if await _already_notified(
                db,
                NotificationEventType.CRITICAL_WORK_UNASSIGNED.value,
                "dedup_key",
                dedup_key,
            ):
                continue
            label = item.task_title or brief_title
            try:
                await dispatcher.emit(
                    NotificationEventType.CRITICAL_WORK_UNASSIGNED.value,
                    payload={
                        "dedup_key": dedup_key,
                        "brief_id": str(item.brief_id),
                        "brief_title": brief_title,
                        "task_id": str(item.task_id) if item.task_id else None,
                        "deadline": deadline,
                        "summary": (
                            f"'{label}' işi {deadline} tarihine kadar teslim edilmeli "
                            "ama kimseye atanmamış."
                        ),
                    },
                    agency_id=agency_id,
                    brand_id=None,
                    actor_user_id=None,
                    recipient_ids=recipient_ids,
                )
                await db.commit()
            except Exception:
                await db.rollback()
                log.exception("Failed to send CRITICAL_WORK_UNASSIGNED for brief %s", item.brief_id)


async def run_finance_capacity_checks() -> None:
    """Runs all five finance/capacity notification checks against a single
    fresh session, each independently wrapped so one check's failure never
    blocks the others — mirrors `run_time_tracking_checks`."""
    async with AsyncSessionLocal() as db:
        for check in (
            _check_capacity_over_threshold,
            _check_commercial_terms_expiring,
            _check_invoice_overdue,
            _check_invoice_due_soon,
            _check_critical_work_unassigned,
        ):
            try:
                await check(db)
            except Exception:
                await db.rollback()
                log.exception("Unexpected error in finance/capacity check %s", check.__name__)


async def _scheduler_loop() -> None:
    """Runs the finance/capacity checks once per hour."""
    while True:
        try:
            await run_finance_capacity_checks()
        except Exception:
            log.exception("Unexpected error in finance/capacity scheduler")
        await asyncio.sleep(60 * 60)


def start_finance_capacity_scheduler() -> asyncio.Task[None]:
    """Schedule the finance/capacity notification loop as a background
    asyncio task."""
    return asyncio.create_task(_scheduler_loop(), name="finance_capacity_scheduler")

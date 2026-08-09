"""Phase 7 notification-wiring tests (plan §14): INVOICE_SENT reaches the
brand's own users, TIME_OFF_APPROVED/REJECTED reach the requester,
RETAINER_OVERAGE dedupes to at most one notification per (brand, period)
even across repeated reads, and no notification title/body/payload ever
carries a cost-rate or credential value."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.client_invoice import ClientInvoice
from app.models.commercial_terms import CommercialTerms, MemberCostRate
from app.models.enums import (
    AgencyMemberRole,
    AgencyMemberStatus,
    BrandMemberRole,
    BrandMemberStatus,
    ClientInvoiceDocumentType,
    ClientInvoiceStatus,
    CommercialTermsBillingModel,
    NotificationEventType,
    TimeOffStatus,
    UserType,
)
from app.models.notification import Notification, NotificationEvent
from app.models.time_entry import TimeEntry
from app.models.time_off import TimeOff
from app.models.user import User
from app.schemas.client_invoice import ClientInvoiceDraftCreate
from app.schemas.time_off import TimeOffReject
from app.services.client_invoice_service import ClientInvoiceService
from app.services.finance_capacity_scheduler import run_finance_capacity_checks
from app.services.retainer_service import RetainerService
from app.services.time_off_service import TimeOffService

TODAY = date.today()

# A distinctive, never-reused cost-rate value: if this literal ever shows up
# in a notification title/body/payload, a cost figure has leaked.
_SECRET_COST_RATE_CENTS = 913377
_SECRET_CREDENTIAL_VALUE = "sk-super-secret-connector-token-should-never-leak"


async def _make_user(session, label: str, user_type: str = UserType.AGENCY_USER.value) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{label.lower()}-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="not-a-real-hash-test-fixture-only",
        full_name=f"Test {label}",
        user_type=user_type,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    return user


async def _seed(label: str, *, hourly_rate_cents: int | None = 50_000) -> dict:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        agency = Agency(id=uuid.uuid4(), name=f"{label} Agency", slug=f"{label.lower()}-{suffix}")
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name=f"{label} Brand",
            slug=f"{label.lower()}-brand-{suffix}",
        )
        session.add_all([agency, brand])
        await session.flush()

        owner = await _make_user(session, f"{label}Owner")
        member = await _make_user(session, f"{label}Member")
        brand_manager = await _make_user(
            session, f"{label}BrandMgr", user_type=UserType.BRAND_USER.value
        )
        await session.flush()

        session.add_all(
            [
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=owner.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=member.id,
                    role=AgencyMemberRole.DESIGNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                BrandMember(
                    id=uuid.uuid4(),
                    brand_id=brand.id,
                    user_id=brand_manager.id,
                    role=BrandMemberRole.BRAND_MANAGER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                ),
            ]
        )

        if hourly_rate_cents is not None:
            session.add(
                CommercialTerms(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    brand_id=brand.id,
                    billing_model=CommercialTermsBillingModel.HOURLY.value,
                    currency="TRY",
                    hourly_rate_cents=hourly_rate_cents,
                    payment_terms_days=30,
                    tax_rate_bps=2000,
                    valid_from=TODAY - timedelta(days=60),
                    active=True,
                )
            )

        await session.commit()
        return {
            "agency_id": agency.id,
            "brand_id": brand.id,
            "owner_id": owner.id,
            "member_id": member.id,
            "brand_manager_id": brand_manager.id,
        }


async def _make_time_entry(
    agency_id: uuid.UUID, brand_id: uuid.UUID, user_id: uuid.UUID, *, hours: float = 2.0
) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        started = datetime.now(UTC) - timedelta(hours=hours + 1)
        ended = started + timedelta(hours=hours)
        entry = TimeEntry(
            id=uuid.uuid4(),
            agency_id=agency_id,
            brand_id=brand_id,
            user_id=user_id,
            category="design",
            description="Test work",
            started_at=started,
            ended_at=ended,
            duration_seconds=int(hours * 3600),
            billable=True,
            source="manual",
            locked=True,
        )
        session.add(entry)
        await session.commit()
        return entry.id


async def _notifications_for(user_id: uuid.UUID, event_type: str) -> list[Notification]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Notification).where(
                Notification.user_id == user_id, Notification.event_type == event_type
            )
        )
        return list(result.scalars().all())


async def _events_of_type(event_type: str) -> list[NotificationEvent]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NotificationEvent).where(NotificationEvent.event_type == event_type)
        )
        return list(result.scalars().all())


# ── INVOICE_SENT ─────────────────────────────────────────────────────────────


async def test_invoice_sent_notifies_brand_recipients_not_agency() -> None:
    ctx = await _seed("InvSent")
    entry_id = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"])

    async with AsyncSessionLocal() as session:
        svc = ClientInvoiceService(session)
        invoice = await svc.generate_draft(
            ctx["agency_id"],
            ctx["owner_id"],
            ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
        )
        invoice = await svc.approve(ctx["agency_id"], invoice.id, ctx["owner_id"])
        await svc.send(ctx["agency_id"], invoice.id)

    brand_notifs = await _notifications_for(
        ctx["brand_manager_id"], NotificationEventType.INVOICE_SENT.value
    )
    assert len(brand_notifs) == 1
    assert invoice.invoice_number in brand_notifs[0].body

    # The agency-side owner who sent it is never notified about their own action.
    owner_notifs = await _notifications_for(
        ctx["owner_id"], NotificationEventType.INVOICE_SENT.value
    )
    assert owner_notifs == []


# ── TIME_OFF_APPROVED / TIME_OFF_REJECTED ───────────────────────────────────


async def _create_time_off(
    agency_id: uuid.UUID, user_id: uuid.UUID, *, offset_days: int
) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        start = datetime.now(UTC) + timedelta(days=offset_days)
        time_off = TimeOff(
            id=uuid.uuid4(),
            agency_id=agency_id,
            user_id=user_id,
            start_at=start,
            end_at=start + timedelta(hours=8),
            all_day=False,
            type="vacation",
            status=TimeOffStatus.REQUESTED.value,
        )
        session.add(time_off)
        await session.commit()
        return time_off.id


async def test_time_off_approval_notifies_requester() -> None:
    ctx = await _seed("TOApprove", hourly_rate_cents=None)
    time_off_id = await _create_time_off(ctx["agency_id"], ctx["member_id"], offset_days=10)

    async with AsyncSessionLocal() as session:
        await TimeOffService(session).approve(ctx["agency_id"], time_off_id, ctx["owner_id"])

    notifs = await _notifications_for(
        ctx["member_id"], NotificationEventType.TIME_OFF_APPROVED.value
    )
    assert len(notifs) == 1


async def test_time_off_rejection_notifies_requester() -> None:
    ctx = await _seed("TOReject", hourly_rate_cents=None)
    time_off_id = await _create_time_off(ctx["agency_id"], ctx["member_id"], offset_days=11)

    async with AsyncSessionLocal() as session:
        await TimeOffService(session).reject(
            ctx["agency_id"], time_off_id, ctx["owner_id"], TimeOffReject(notes="Yoğun dönem")
        )

    notifs = await _notifications_for(
        ctx["member_id"], NotificationEventType.TIME_OFF_REJECTED.value
    )
    assert len(notifs) == 1


# ── RETAINER_OVERAGE dedupe ──────────────────────────────────────────────────


async def test_retainer_overage_dedupes_within_same_period() -> None:
    ctx = await _seed("Retainer", hourly_rate_cents=None)
    async with AsyncSessionLocal() as session:
        session.add(
            CommercialTerms(
                id=uuid.uuid4(),
                agency_id=ctx["agency_id"],
                brand_id=ctx["brand_id"],
                billing_model=CommercialTermsBillingModel.RETAINER.value,
                currency="TRY",
                retainer_included_minutes=60,
                overage_rate_cents=10_000,
                payment_terms_days=30,
                tax_rate_bps=2000,
                valid_from=TODAY - timedelta(days=5),
                active=True,
            )
        )
        await session.commit()

    # 3 hours logged this period, included is only 60 minutes -> clear overage.
    await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"], hours=3.0)

    async with AsyncSessionLocal() as session:
        summary_1 = await RetainerService(session).get_current_period_summary(
            ctx["agency_id"], ctx["brand_id"]
        )
    assert summary_1.overage_minutes > 0

    async with AsyncSessionLocal() as session:
        summary_2 = await RetainerService(session).get_current_period_summary(
            ctx["agency_id"], ctx["brand_id"]
        )
    assert summary_2.overage_minutes == summary_1.overage_minutes

    events = await _events_of_type(NotificationEventType.RETAINER_OVERAGE.value)
    matching = [e for e in events if e.brand_id == ctx["brand_id"]]
    assert len(matching) == 1, "calling the summary twice in the same period must not double-notify"

    owner_notifs = await _notifications_for(
        ctx["owner_id"], NotificationEventType.RETAINER_OVERAGE.value
    )
    assert len(owner_notifs) == 1


# ── No cost/rate/credential leakage ──────────────────────────────────────────


async def test_no_notification_body_or_payload_contains_cost_rate_or_credential_values() -> None:
    """Builds one invoice-sent notification (the richest payload of the
    Phase 7 events) using a distinctive, never-elsewhere-used cost-rate cents
    value and asserts that value — and a stand-in credential string — never
    appear in any Notification title/body or NotificationEvent payload."""
    ctx = await _seed("NoLeak")
    async with AsyncSessionLocal() as session:
        session.add(
            MemberCostRate(
                id=uuid.uuid4(),
                agency_id=ctx["agency_id"],
                user_id=ctx["member_id"],
                currency="TRY",
                hourly_cost_cents=_SECRET_COST_RATE_CENTS,
                valid_from=TODAY - timedelta(days=60),
                active=True,
            )
        )
        await session.commit()

    entry_id = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"])

    async with AsyncSessionLocal() as session:
        svc = ClientInvoiceService(session)
        invoice = await svc.generate_draft(
            ctx["agency_id"],
            ctx["owner_id"],
            ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
        )
        invoice = await svc.approve(ctx["agency_id"], invoice.id, ctx["owner_id"])
        await svc.send(ctx["agency_id"], invoice.id)

    async with AsyncSessionLocal() as session:
        notif_result = await session.execute(
            select(Notification).where(Notification.agency_id == ctx["agency_id"])
        )
        notifications = list(notif_result.scalars().all())
        event_result = await session.execute(
            select(NotificationEvent).where(NotificationEvent.agency_id == ctx["agency_id"])
        )
        events = list(event_result.scalars().all())

    secret_str = str(_SECRET_COST_RATE_CENTS)
    for n in notifications:
        assert secret_str not in n.title
        assert secret_str not in n.body
        assert _SECRET_CREDENTIAL_VALUE not in n.title
        assert _SECRET_CREDENTIAL_VALUE not in n.body
    for e in events:
        payload_str = str(e.payload)
        assert secret_str not in payload_str, f"{e.event_type} payload leaked a cost-rate value"
        assert _SECRET_CREDENTIAL_VALUE not in payload_str
        for forbidden_key in ("cost_rate_cents", "hourly_cost_cents", "encrypted_credentials"):
            assert forbidden_key not in e.payload


# ── Periodic scheduler: INVOICE_OVERDUE / COMMERCIAL_TERMS_EXPIRING ─────────


async def test_scheduler_flags_overdue_invoice() -> None:
    ctx = await _seed("Overdue", hourly_rate_cents=None)
    async with AsyncSessionLocal() as session:
        session.add(
            ClientInvoice(
                id=uuid.uuid4(),
                agency_id=ctx["agency_id"],
                brand_id=ctx["brand_id"],
                invoice_number=f"OD-{uuid.uuid4().hex[:8]}",
                document_type=ClientInvoiceDocumentType.DRAFT_INVOICE.value,
                issue_date=TODAY - timedelta(days=40),
                due_date=TODAY - timedelta(days=10),
                currency="TRY",
                subtotal_cents=100_000,
                discount_cents=0,
                tax_cents=20_000,
                total_cents=120_000,
                status=ClientInvoiceStatus.SENT.value,
            )
        )
        await session.commit()

    await run_finance_capacity_checks()

    notifs = await _notifications_for(ctx["owner_id"], NotificationEventType.INVOICE_OVERDUE.value)
    assert len(notifs) == 1

    # A second run within the dedupe window must not double-notify.
    await run_finance_capacity_checks()
    notifs_again = await _notifications_for(
        ctx["owner_id"], NotificationEventType.INVOICE_OVERDUE.value
    )
    assert len(notifs_again) == 1


async def test_scheduler_flags_expiring_commercial_terms() -> None:
    ctx = await _seed("Expiring", hourly_rate_cents=None)
    async with AsyncSessionLocal() as session:
        session.add(
            CommercialTerms(
                id=uuid.uuid4(),
                agency_id=ctx["agency_id"],
                brand_id=ctx["brand_id"],
                billing_model=CommercialTermsBillingModel.FIXED_FEE.value,
                currency="TRY",
                fixed_fee_cents=500_000,
                payment_terms_days=30,
                tax_rate_bps=2000,
                valid_from=TODAY - timedelta(days=300),
                valid_until=TODAY + timedelta(days=5),
                active=True,
            )
        )
        await session.commit()

    await run_finance_capacity_checks()

    notifs = await _notifications_for(
        ctx["owner_id"], NotificationEventType.COMMERCIAL_TERMS_EXPIRING.value
    )
    assert len(notifs) == 1
    assert str(_SECRET_COST_RATE_CENTS) not in notifs[0].body
    assert "500000" not in notifs[0].body and "500_000" not in notifs[0].body

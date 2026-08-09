"""Backend tests for WhatsApp domain-event routing (Part 6B-1).

Covers the layer NotificationDispatcher._dispatch_whatsapp adds on top of
the already-tested in-app/email fan-out: approved-template gating,
allowlisted/sanitized payloads, deep links, role-based WhatsApp-only
narrowing, idempotency, rollback-safety, and the brief/invoice reminder
schedulers. No real Twilio call is ever made — every provider here is a
fake/stub, and WHATSAPP_NOTIFICATIONS_ENABLED stays at its test-env default
(False) except where a test explicitly patches the provider factory.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.time_utils import utc_today
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.brief import Brief
from app.models.client_invoice import ClientInvoice
from app.models.enums import (
    AgencyMemberRole,
    AgencyMemberStatus,
    BrandMemberRole,
    BrandMemberStatus,
    BriefStatus,
    ClientInvoiceDocumentType,
    ClientInvoiceStatus,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
    UserType,
    WhatsAppTemplateStatus,
)
from app.models.notification import Notification, NotificationDelivery, NotificationPreference
from app.models.user import User
from app.repositories.notification import (
    NotificationEventRepository,
    NotificationPreferenceRepository,
)
from app.repositories.whatsapp_template import WhatsAppTemplateRepository
from app.schemas.payment import PaymentCreate
from app.services.deadline_scheduler import run_overdue_check
from app.services.finance_capacity_scheduler import run_finance_capacity_checks
from app.services.notification_dispatcher import NotificationDispatcher
from app.services.payment_service import PaymentService
from app.services.whatsapp_payload_builder import (
    build_variables,
    resolve_deep_link,
    short_safe_preview,
)
from app.services.whatsapp_provider import WhatsAppDeliveryResult
from app.services.whatsapp_recipient_gate import is_whatsapp_role_eligible

TODAY = utc_today()


# ── Fake providers (no real Twilio call ever) ───────────────────────────────


@dataclass
class _FakeSentProvider:
    calls: list[tuple[str, str, dict]] = field(default_factory=list)

    def get_provider_name(self) -> str:
        return "twilio_production"

    def send_template_message(
        self, to_phone: str, content_sid: str, variables: dict[str, str]
    ) -> WhatsAppDeliveryResult:
        self.calls.append((to_phone, content_sid, variables))
        return WhatsAppDeliveryResult(
            status=NotificationDeliveryStatus.SENT.value,
            provider="twilio_production",
            provider_message_id="SMfake" + uuid.uuid4().hex[:8],
            error_message=None,
        )


class _FakeRaisingProvider:
    def get_provider_name(self) -> str:
        return "twilio_production"

    def send_template_message(
        self, to_phone: str, content_sid: str, variables: dict[str, str]
    ) -> WhatsAppDeliveryResult:
        raise RuntimeError("simulated Twilio outage")


def _patched_provider(provider: object):
    return patch(
        "app.services.whatsapp_provider.WhatsAppProviderFactory.get_provider",
        return_value=provider,
    )


# ── Seed helpers ─────────────────────────────────────────────────────────────


async def _make_user(
    session,
    label: str,
    *,
    user_type: str = UserType.AGENCY_USER.value,
    phone_number: str | None = None,
    whatsapp_opt_in: bool = False,
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{label.lower()}-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="not-a-real-hash-test-fixture-only",
        full_name=f"Test {label}",
        user_type=user_type,
        is_active=True,
        is_verified=True,
        phone_number=phone_number,
        whatsapp_opt_in=whatsapp_opt_in,
    )
    session.add(user)
    return user


async def _set_whatsapp_ready(session, user_id: uuid.UUID) -> None:
    """Make a user WhatsApp-eligible: opted-in phone + whatsapp_enabled pref."""
    user = await session.get(User, user_id)
    user.phone_number = "+90555" + str(uuid.uuid4().int)[:7]
    user.whatsapp_opt_in = True
    session.add(user)
    session.add(NotificationPreference(id=uuid.uuid4(), user_id=user_id, whatsapp_enabled=True))


@dataclass
class Ctx:
    agency_id: uuid.UUID
    brand_id: uuid.UUID
    owner_id: uuid.UUID  # agency owner — has INVOICE_VIEW
    designer_id: uuid.UUID  # agency designer — lacks INVOICE_VIEW
    brand_manager_id: uuid.UUID  # brand side — has BRIEF_APPROVE
    brand_viewer_id: uuid.UUID  # brand side — lacks BRIEF_APPROVE
    brief_id: uuid.UUID


async def _seed(label: str, *, is_demo: bool = False, whatsapp_ready: bool = True) -> Ctx:
    suffix = uuid.uuid4().hex[:10]
    async with AsyncSessionLocal() as session:
        agency = Agency(
            id=uuid.uuid4(),
            name=f"{label} Agency",
            slug=f"{label.lower()}-agency-{suffix}",
            is_demo=is_demo,
            demo_expires_at=(datetime.now(UTC) + timedelta(hours=1)) if is_demo else None,
        )
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name=f"{label} Brand",
            slug=f"{label.lower()}-brand-{suffix}",
        )
        session.add_all([agency, brand])

        owner = await _make_user(session, f"{label}Owner")
        designer = await _make_user(session, f"{label}Designer")
        brand_manager = await _make_user(
            session, f"{label}BrandMgr", user_type=UserType.BRAND_USER.value
        )
        brand_viewer = await _make_user(
            session, f"{label}BrandViewer", user_type=UserType.BRAND_USER.value
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
                    user_id=designer.id,
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
                BrandMember(
                    id=uuid.uuid4(),
                    brand_id=brand.id,
                    user_id=brand_viewer.id,
                    role=BrandMemberRole.BRAND_VIEWER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                ),
            ]
        )

        brief = Brief(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand.id,
            title=f"{label} Brief",
            status=BriefStatus.DRAFT.value,
            created_by_id=owner.id,
        )
        session.add(brief)
        await session.flush()

        if whatsapp_ready and not is_demo:
            for uid in (owner.id, designer.id, brand_manager.id, brand_viewer.id):
                await _set_whatsapp_ready(session, uid)

        await session.commit()

        return Ctx(
            agency_id=agency.id,
            brand_id=brand.id,
            owner_id=owner.id,
            designer_id=designer.id,
            brand_manager_id=brand_manager.id,
            brand_viewer_id=brand_viewer.id,
            brief_id=brief.id,
        )


async def _cleanup(ctx: Ctx) -> None:
    async with AsyncSessionLocal() as session:
        agency = await session.get(Agency, ctx.agency_id)
        if agency is not None:
            await session.delete(agency)
        brand = await session.get(Brand, ctx.brand_id)
        if brand is not None:
            await session.delete(brand)
        await session.commit()
        for uid in (ctx.owner_id, ctx.designer_id, ctx.brand_manager_id, ctx.brand_viewer_id):
            user = await session.get(User, uid)
            if user is not None:
                await session.delete(user)
        await session.commit()


@pytest.fixture
async def ctx():
    c = await _seed("Ctx")
    try:
        yield c
    finally:
        await _cleanup(c)


@pytest.fixture
async def demo_ctx():
    c = await _seed("Demo", is_demo=True)
    try:
        yield c
    finally:
        await _cleanup(c)


@pytest.fixture
async def approve_template():
    """Approve a seeded draft template for the duration of one test, then
    restore it to draft — the 16 rows are shared, migration-seeded singletons
    keyed by `code`, not per-test fixtures, so mutating one without restoring
    would leak into every other test that touches the same code."""
    approved: list[str] = []

    async def _approve(code: str, *, content_sid: str, variable_schema: dict[str, str]) -> None:
        async with AsyncSessionLocal() as session:
            repo = WhatsAppTemplateRepository(session)
            tpl = await repo.get_by_code(code)
            assert tpl is not None, f"seed migration must have created whatsapp_templates.{code}"
            tpl.status = WhatsAppTemplateStatus.APPROVED.value
            tpl.content_sid = content_sid
            tpl.variable_schema = variable_schema
            session.add(tpl)
            await session.commit()
        approved.append(code)

    yield _approve

    async with AsyncSessionLocal() as session:
        repo = WhatsAppTemplateRepository(session)
        for code in approved:
            tpl = await repo.get_by_code(code)
            if tpl is not None:
                tpl.status = WhatsAppTemplateStatus.DRAFT.value
                tpl.content_sid = None
                tpl.variable_schema = {}
                session.add(tpl)
        await session.commit()


async def _deliveries_for(event_id: uuid.UUID, channel: str) -> list[NotificationDelivery]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NotificationDelivery).where(
                NotificationDelivery.event_id == event_id,
                NotificationDelivery.channel == channel,
            )
        )
        return list(result.scalars().all())


async def _deliveries_for_events(
    event_ids: list[uuid.UUID], channel: str
) -> list[NotificationDelivery]:
    """Like _deliveries_for, but spanning several NotificationEvent rows —
    used by the domain-level dedupe tests, where the same real action is
    deliberately emitted as two separate NotificationEvent rows and the
    assertion is that at most one WhatsApp delivery exists across *both*."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NotificationDelivery).where(
                NotificationDelivery.event_id.in_(event_ids),
                NotificationDelivery.channel == channel,
            )
        )
        return list(result.scalars().all())


async def _notifications_for(user_id: uuid.UUID, event_type: str) -> list[Notification]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Notification).where(
                Notification.user_id == user_id, Notification.event_type == event_type
            )
        )
        return list(result.scalars().all())


# ── Gating chain: demo / consent / phone ────────────────────────────────────


async def test_demo_tenant_skips_whatsapp_but_not_in_app(demo_ctx: Ctx) -> None:
    async with AsyncSessionLocal() as session:
        event = await NotificationDispatcher(session).emit(
            NotificationEventType.BRIEF_CREATED.value,
            payload={"brief_id": str(demo_ctx.brief_id), "brief_title": "Demo Brief"},
            agency_id=demo_ctx.agency_id,
            brand_id=demo_ctx.brand_id,
            actor_user_id=None,
            recipient_ids=[demo_ctx.owner_id],
        )
        await session.commit()

    wa = await _deliveries_for(event.id, NotificationChannel.WHATSAPP.value)
    assert len(wa) == 1
    assert wa[0].status == NotificationDeliveryStatus.SKIPPED_DEMO_TENANT.value

    notifs = await _notifications_for(demo_ctx.owner_id, NotificationEventType.BRIEF_CREATED.value)
    assert len(notifs) == 1  # in-app unaffected by the WhatsApp skip


async def test_no_consent_skips_whatsapp(ctx: Ctx) -> None:
    async with AsyncSessionLocal() as session:
        user = await session.get(User, ctx.designer_id)
        user.whatsapp_opt_in = False
        session.add(user)
        await session.commit()

        event = await NotificationDispatcher(session).emit(
            NotificationEventType.BRIEF_CREATED.value,
            payload={"brief_id": str(ctx.brief_id), "brief_title": ctx.brief_id.hex},
            agency_id=ctx.agency_id,
            brand_id=ctx.brand_id,
            actor_user_id=None,
            recipient_ids=[ctx.designer_id],
        )
        await session.commit()

    wa = await _deliveries_for(event.id, NotificationChannel.WHATSAPP.value)
    assert len(wa) == 1
    assert wa[0].status == NotificationDeliveryStatus.SKIPPED_NO_CONSENT.value


async def test_no_phone_skips_whatsapp(ctx: Ctx) -> None:
    async with AsyncSessionLocal() as session:
        user = await session.get(User, ctx.owner_id)
        user.phone_number = None
        session.add(user)
        await session.commit()

        event = await NotificationDispatcher(session).emit(
            NotificationEventType.BRIEF_CREATED.value,
            payload={"brief_id": str(ctx.brief_id), "brief_title": "X"},
            agency_id=ctx.agency_id,
            brand_id=ctx.brand_id,
            actor_user_id=None,
            recipient_ids=[ctx.owner_id],
        )
        await session.commit()

    wa = await _deliveries_for(event.id, NotificationChannel.WHATSAPP.value)
    assert wa[0].status == NotificationDeliveryStatus.SKIPPED_NO_PHONE.value


async def test_actor_never_notified_on_own_action(ctx: Ctx) -> None:
    async with AsyncSessionLocal() as session:
        event = await NotificationDispatcher(session).emit(
            NotificationEventType.BRIEF_CREATED.value,
            payload={"brief_id": str(ctx.brief_id), "brief_title": "X"},
            agency_id=ctx.agency_id,
            brand_id=ctx.brand_id,
            actor_user_id=ctx.owner_id,
            recipient_ids=[ctx.owner_id, ctx.designer_id],
        )
        await session.commit()

    wa = await _deliveries_for(event.id, NotificationChannel.WHATSAPP.value)
    # Only the designer (non-actor) gets a delivery row at all.
    assert len(wa) == 1
    notifs = await _notifications_for(ctx.owner_id, NotificationEventType.BRIEF_CREATED.value)
    assert notifs == []


# ── Template registry gating ────────────────────────────────────────────────


async def test_missing_template_skips_whatsapp_in_app_still_sent(ctx: Ctx) -> None:
    async with AsyncSessionLocal() as session:
        event = await NotificationDispatcher(session).emit(
            NotificationEventType.BRIEF_CREATED.value,
            payload={"brief_id": str(ctx.brief_id), "brief_title": "No Template Yet"},
            agency_id=ctx.agency_id,
            brand_id=ctx.brand_id,
            actor_user_id=None,
            recipient_ids=[ctx.owner_id],
        )
        await session.commit()

    wa = await _deliveries_for(event.id, NotificationChannel.WHATSAPP.value)
    assert wa[0].status == NotificationDeliveryStatus.SKIPPED_TEMPLATE_MISSING.value
    assert wa[0].template_key == "brief_created"

    notifs = await _notifications_for(ctx.owner_id, NotificationEventType.BRIEF_CREATED.value)
    assert len(notifs) == 1  # email/in-app never depend on WhatsApp template state


async def test_disabled_template_is_treated_as_missing(ctx: Ctx) -> None:
    async with AsyncSessionLocal() as session:
        repo = WhatsAppTemplateRepository(session)
        tpl = await repo.get_by_code("comment_added")
        tpl.status = WhatsAppTemplateStatus.DISABLED.value
        tpl.content_sid = "HXsomethingdisabled"
        session.add(tpl)
        await session.commit()

    try:
        async with AsyncSessionLocal() as session:
            event = await NotificationDispatcher(session).emit(
                NotificationEventType.COMMENT_ADDED.value,
                payload={
                    "brief_id": str(ctx.brief_id),
                    "brief_title": "X",
                    "comment_id": str(uuid.uuid4()),
                    "comment_preview": "hello",
                },
                agency_id=ctx.agency_id,
                brand_id=ctx.brand_id,
                actor_user_id=None,
                recipient_ids=[ctx.owner_id],
            )
            await session.commit()

        wa = await _deliveries_for(event.id, NotificationChannel.WHATSAPP.value)
        assert wa[0].status == NotificationDeliveryStatus.SKIPPED_TEMPLATE_MISSING.value
    finally:
        async with AsyncSessionLocal() as session:
            repo = WhatsAppTemplateRepository(session)
            tpl = await repo.get_by_code("comment_added")
            tpl.status = WhatsAppTemplateStatus.DRAFT.value
            tpl.content_sid = None
            session.add(tpl)
            await session.commit()


async def test_approved_template_sends_via_content_sid_not_freeform(
    ctx: Ctx, approve_template
) -> None:
    await approve_template(
        "brief_created",
        content_sid="HXapprovedbriefcreated",
        variable_schema={"1": "recipient_first_name", "2": "brief_title", "3": "deep_link_url"},
    )
    fake = _FakeSentProvider()
    with _patched_provider(fake):
        async with AsyncSessionLocal() as session:
            event = await NotificationDispatcher(session).emit(
                NotificationEventType.BRIEF_CREATED.value,
                payload={"brief_id": str(ctx.brief_id), "brief_title": "Approved Flow Brief"},
                agency_id=ctx.agency_id,
                brand_id=ctx.brand_id,
                actor_user_id=None,
                recipient_ids=[ctx.owner_id],
            )
            await session.commit()

    wa = await _deliveries_for(event.id, NotificationChannel.WHATSAPP.value)
    assert wa[0].status == NotificationDeliveryStatus.SENT.value
    assert wa[0].provider_message_id is not None
    assert len(fake.calls) == 1
    to_phone, content_sid, variables = fake.calls[0]
    assert content_sid == "HXapprovedbriefcreated"
    assert variables["2"] == "Approved Flow Brief"
    assert "dashboard/briefs" in variables["3"]


async def test_provider_failure_does_not_raise_or_block_other_channels(
    ctx: Ctx, approve_template
) -> None:
    await approve_template(
        "brief_created",
        content_sid="HXwillfail",
        variable_schema={"1": "brief_title"},
    )
    with _patched_provider(_FakeRaisingProvider()):
        async with AsyncSessionLocal() as session:
            # emit() must return normally — a WhatsApp provider exception
            # must never propagate into the caller's transaction.
            event = await NotificationDispatcher(session).emit(
                NotificationEventType.BRIEF_CREATED.value,
                payload={"brief_id": str(ctx.brief_id), "brief_title": "Will Fail"},
                agency_id=ctx.agency_id,
                brand_id=ctx.brand_id,
                actor_user_id=None,
                recipient_ids=[ctx.owner_id],
            )
            await session.commit()

    wa = await _deliveries_for(event.id, NotificationChannel.WHATSAPP.value)
    assert wa[0].status == NotificationDeliveryStatus.FAILED.value

    notifs = await _notifications_for(ctx.owner_id, NotificationEventType.BRIEF_CREATED.value)
    assert len(notifs) == 1  # in-app succeeded despite the WhatsApp provider exploding


async def test_idempotency_key_prevents_duplicate_send(ctx: Ctx, approve_template) -> None:
    await approve_template(
        "brief_created", content_sid="HXidem", variable_schema={"1": "brief_title"}
    )
    fake = _FakeSentProvider()
    with _patched_provider(fake):
        async with AsyncSessionLocal() as session:
            dispatcher = NotificationDispatcher(session)
            event = await dispatcher.emit(
                NotificationEventType.BRIEF_CREATED.value,
                payload={"brief_id": str(ctx.brief_id), "brief_title": "Idempotent"},
                agency_id=ctx.agency_id,
                brand_id=ctx.brand_id,
                actor_user_id=None,
                recipient_ids=[ctx.owner_id],
            )
            await session.commit()

            # Re-dispatch the SAME event/recipient pair (simulates a
            # hypothetical retry/outbox reprocessing this NotificationEvent).
            user = await session.get(User, ctx.owner_id)
            pref = await NotificationPreferenceRepository(session).get_or_create(ctx.owner_id)
            await dispatcher._dispatch_whatsapp(
                event=event,
                user=user,
                pref=pref,
                demo_sandbox=False,
                wa_provider=fake,
                actor_user=None,
            )
            await session.commit()

    wa = await _deliveries_for(event.id, NotificationChannel.WHATSAPP.value)
    assert len(wa) == 1, "a second dispatch for the same event+recipient+channel must be a no-op"
    assert len(fake.calls) == 1


# ── Role-based WhatsApp-only narrowing ──────────────────────────────────────


async def test_approval_requested_only_reaches_brief_approve_role(
    ctx: Ctx, approve_template
) -> None:
    await approve_template(
        "approval_requested", content_sid="HXapproval", variable_schema={"1": "brief_title"}
    )
    fake = _FakeSentProvider()
    with _patched_provider(fake):
        async with AsyncSessionLocal() as session:
            event = await NotificationDispatcher(session).emit(
                NotificationEventType.BRIEF_SUBMITTED.value,
                payload={"brief_id": str(ctx.brief_id), "brief_title": "Needs Approval"},
                agency_id=ctx.agency_id,
                brand_id=ctx.brand_id,
                actor_user_id=None,
                recipient_ids=[ctx.brand_manager_id, ctx.brand_viewer_id],
            )
            await session.commit()

    wa = await _deliveries_for(event.id, NotificationChannel.WHATSAPP.value)
    assert len(fake.calls) == 1  # only brand_manager (BRIEF_APPROVE) actually sent
    statuses = {d.status for d in wa}
    assert NotificationDeliveryStatus.SENT.value in statuses
    assert NotificationDeliveryStatus.SKIPPED.value in statuses

    # Both still get the in-app nudge — only WhatsApp is narrowed.
    assert (
        len(
            await _notifications_for(
                ctx.brand_manager_id, NotificationEventType.BRIEF_SUBMITTED.value
            )
        )
        == 1
    )
    assert (
        len(
            await _notifications_for(
                ctx.brand_viewer_id, NotificationEventType.BRIEF_SUBMITTED.value
            )
        )
        == 1
    )


async def test_is_whatsapp_role_eligible_fails_closed_cross_tenant() -> None:
    """A recipient with no membership row at all for the event's
    agency/brand (e.g. a caller bug passing a foreign user id) must never be
    treated as eligible — fail-closed, not fail-open."""
    ctx_a = await _seed("RoleA")
    ctx_b = await _seed("RoleB")
    try:
        async with AsyncSessionLocal() as session:
            from app.models.notification import NotificationEvent

            event = NotificationEvent(
                id=uuid.uuid4(),
                event_type=NotificationEventType.INVOICE_PAYMENT_RECEIVED.value,
                payload={},
                agency_id=ctx_a.agency_id,
            )
            session.add(event)
            await session.flush()

            foreign_user = await session.get(User, ctx_b.owner_id)
            eligible = await is_whatsapp_role_eligible(session, event, foreign_user)
            assert eligible is False
    finally:
        await _cleanup(ctx_a)
        await _cleanup(ctx_b)


# ── Payload allowlist / sanitization ────────────────────────────────────────


def test_short_safe_preview_strips_html_and_truncates() -> None:
    raw = "<script>alert(1)</script>Hello\nworld  " + ("x" * 100)
    preview = short_safe_preview(raw)
    assert "<script>" not in preview
    assert "<" not in preview
    assert len(preview) <= 80
    assert "\n" not in preview


async def test_build_variables_never_leaks_full_reason_or_cost_fields(ctx: Ctx) -> None:
    from app.models.notification import NotificationEvent

    long_reason = "Gizli iç maliyet detayları: " + ("A" * 300)
    event = NotificationEvent(
        id=uuid.uuid4(),
        event_type=NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value,
        payload={
            "brief_id": str(ctx.brief_id),
            "brief_title": "Reason Test",
            "deliverable_id": str(uuid.uuid4()),
            "deliverable_title": "V1",
            "reason": long_reason,
        },
        agency_id=ctx.agency_id,
        brand_id=ctx.brand_id,
    )
    async with AsyncSessionLocal() as session:
        recipient = await session.get(User, ctx.owner_id)
        variables = build_variables(event, recipient)

    assert set(variables) <= {
        "recipient_first_name",
        "actor_display_name",
        "brief_title",
        "brand_name",
        "deliverable_title",
        "due_date",
        "invoice_number",
        "invoice_total_formatted",
        "short_safe_summary",
        "deep_link_url",
    }
    assert long_reason not in variables["short_safe_summary"]
    assert len(variables["short_safe_summary"]) <= 80
    assert "cost_rate" not in str(variables)
    assert "profitability" not in str(variables)


# ── Deep links ───────────────────────────────────────────────────────────────


async def test_deep_link_routes_agency_vs_brand_and_entity_type(ctx: Ctx) -> None:
    from app.models.notification import NotificationEvent

    async with AsyncSessionLocal() as session:
        agency_user = await session.get(User, ctx.owner_id)
        brand_user = await session.get(User, ctx.brand_manager_id)

        brief_event = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.BRIEF_CREATED.value,
            payload={"brief_id": str(ctx.brief_id)},
            agency_id=ctx.agency_id,
        )
        agency_link = resolve_deep_link(brief_event, agency_user)
        brand_link = resolve_deep_link(brief_event, brand_user)
        assert f"/dashboard/briefs/{ctx.brief_id}" in agency_link
        assert f"/brand/briefs/{ctx.brief_id}" in brand_link

        deliverable_id = uuid.uuid4()
        deliverable_event = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.DELIVERABLE_SUBMITTED.value,
            payload={"brief_id": str(ctx.brief_id), "deliverable_id": str(deliverable_id)},
            agency_id=ctx.agency_id,
        )
        link = resolve_deep_link(deliverable_event, brand_user)
        assert f"deliverable={deliverable_id}" in link

        annotation_id = uuid.uuid4()
        annotation_event = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.ANNOTATION_CREATED.value,
            payload={
                "brief_id": str(ctx.brief_id),
                "deliverable_id": str(deliverable_id),
                "annotation_id": str(annotation_id),
            },
            agency_id=ctx.agency_id,
        )
        link = resolve_deep_link(annotation_event, agency_user)
        assert f"annotation={annotation_id}" in link

        invoice_id = uuid.uuid4()
        invoice_event = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.INVOICE_SENT.value,
            payload={"invoice_id": str(invoice_id)},
            agency_id=ctx.agency_id,
        )
        agency_invoice_link = resolve_deep_link(invoice_event, agency_user)
        brand_invoice_link = resolve_deep_link(invoice_event, brand_user)
        assert f"/dashboard/finance/invoices/{invoice_id}" in agency_invoice_link
        assert f"/brand/invoices/{invoice_id}" in brand_invoice_link
        # Never derived from anything user-supplied — only server-side payload ids.
        assert str(invoice_id) not in (agency_link, brand_link)


# ── brief.overdue scheduler ─────────────────────────────────────────────────


async def _make_brief(
    agency_id: uuid.UUID,
    brand_id: uuid.UUID,
    *,
    deadline: str,
    status: str,
    created_by_id: uuid.UUID,
) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        brief = Brief(
            id=uuid.uuid4(),
            agency_id=agency_id,
            brand_id=brand_id,
            title=f"Overdue Test {uuid.uuid4().hex[:6]}",
            status=status,
            deadline=deadline,
            created_by_id=created_by_id,
        )
        session.add(brief)
        await session.commit()
        return brief.id


async def test_overdue_scheduler_flags_past_deadline_brief(ctx: Ctx) -> None:
    past = (TODAY - timedelta(days=2)).isoformat()
    await _make_brief(
        ctx.agency_id,
        ctx.brand_id,
        deadline=past,
        status=BriefStatus.DRAFT.value,
        created_by_id=ctx.owner_id,
    )

    await run_overdue_check()

    notifs = await _notifications_for(ctx.owner_id, NotificationEventType.BRIEF_OVERDUE.value)
    assert len(notifs) >= 1

    # Re-running within the dedupe window must not double-notify.
    await run_overdue_check()
    notifs_again = await _notifications_for(ctx.owner_id, NotificationEventType.BRIEF_OVERDUE.value)
    assert len(notifs_again) == len(notifs)


async def test_overdue_scheduler_excludes_archived_and_approved_briefs(ctx: Ctx) -> None:
    past = (TODAY - timedelta(days=5)).isoformat()
    archived_id = await _make_brief(
        ctx.agency_id,
        ctx.brand_id,
        deadline=past,
        status=BriefStatus.ARCHIVED.value,
        created_by_id=ctx.owner_id,
    )
    approved_id = await _make_brief(
        ctx.agency_id,
        ctx.brand_id,
        deadline=past,
        status=BriefStatus.APPROVED.value,
        created_by_id=ctx.owner_id,
    )

    await run_overdue_check()

    from app.models.notification import NotificationEvent

    async with AsyncSessionLocal() as session:
        for brief_id in (archived_id, approved_id):
            result = await session.execute(
                select(NotificationEvent).where(
                    NotificationEvent.event_type == NotificationEventType.BRIEF_OVERDUE.value,
                    NotificationEvent.payload["brief_id"].astext == str(brief_id),
                )
            )
            assert result.scalar_one_or_none() is None


# ── invoice.due_soon / invoice.overdue mutual exclusivity ──────────────────


async def _make_invoice(
    agency_id: uuid.UUID,
    brand_id: uuid.UUID,
    *,
    due_date,
    status: str,
    total_cents: int = 120_000,
) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        invoice = ClientInvoice(
            id=uuid.uuid4(),
            agency_id=agency_id,
            brand_id=brand_id,
            invoice_number=f"WA-{uuid.uuid4().hex[:8]}",
            document_type=ClientInvoiceDocumentType.DRAFT_INVOICE.value,
            issue_date=TODAY - timedelta(days=20),
            due_date=due_date,
            currency="TRY",
            subtotal_cents=total_cents,
            discount_cents=0,
            tax_cents=0,
            total_cents=total_cents,
            status=status,
        )
        session.add(invoice)
        await session.commit()
        return invoice.id


async def test_invoice_due_soon_notifies_brand_not_agency(ctx: Ctx) -> None:
    await _make_invoice(
        ctx.agency_id,
        ctx.brand_id,
        due_date=TODAY + timedelta(days=2),
        status=ClientInvoiceStatus.SENT.value,
    )

    await run_finance_capacity_checks()

    brand_notifs = await _notifications_for(
        ctx.brand_manager_id, NotificationEventType.INVOICE_DUE_SOON.value
    )
    assert len(brand_notifs) == 1
    owner_notifs = await _notifications_for(
        ctx.owner_id, NotificationEventType.INVOICE_DUE_SOON.value
    )
    assert owner_notifs == []


async def test_paid_invoice_excluded_from_due_soon_and_overdue(ctx: Ctx) -> None:
    await _make_invoice(
        ctx.agency_id,
        ctx.brand_id,
        due_date=TODAY - timedelta(days=3),
        status=ClientInvoiceStatus.PAID.value,
    )
    await _make_invoice(
        ctx.agency_id,
        ctx.brand_id,
        due_date=TODAY + timedelta(days=1),
        status=ClientInvoiceStatus.PAID.value,
    )

    await run_finance_capacity_checks()

    assert (
        await _notifications_for(ctx.owner_id, NotificationEventType.INVOICE_OVERDUE.value) == []
    )
    assert (
        await _notifications_for(ctx.brand_manager_id, NotificationEventType.INVOICE_DUE_SOON.value)
        == []
    )


async def test_invoice_due_soon_and_overdue_are_mutually_exclusive(ctx: Ctx) -> None:
    await _make_invoice(
        ctx.agency_id,
        ctx.brand_id,
        due_date=TODAY - timedelta(days=1),
        status=ClientInvoiceStatus.SENT.value,
    )

    await run_finance_capacity_checks()

    assert (
        len(await _notifications_for(ctx.owner_id, NotificationEventType.INVOICE_OVERDUE.value))
        == 1
    )
    assert (
        await _notifications_for(ctx.brand_manager_id, NotificationEventType.INVOICE_DUE_SOON.value)
        == []
    )


# ── invoice.payment_received ────────────────────────────────────────────────


async def test_payment_received_notifies_only_invoice_view_role(ctx: Ctx) -> None:
    from app.models.enums import PaymentMethod

    invoice_id = await _make_invoice(
        ctx.agency_id,
        ctx.brand_id,
        due_date=TODAY + timedelta(days=10),
        status=ClientInvoiceStatus.SENT.value,
        total_cents=100_000,
    )

    async with AsyncSessionLocal() as session:
        svc = PaymentService(session)
        await svc.record_payment(
            ctx.agency_id,
            ctx.owner_id,
            PaymentCreate(
                brand_id=ctx.brand_id,
                invoice_id=invoice_id,
                amount_cents=100_000,
                currency="TRY",
                payment_method=PaymentMethod.BANK_TRANSFER.value,
                paid_at=datetime.now(UTC),
            ),
        )

    owner_notifs = await _notifications_for(
        ctx.owner_id, NotificationEventType.INVOICE_PAYMENT_RECEIVED.value
    )
    assert len(owner_notifs) == 1  # OWNER holds invoice:view

    designer_notifs = await _notifications_for(
        ctx.designer_id, NotificationEventType.INVOICE_PAYMENT_RECEIVED.value
    )
    assert designer_notifs == []  # DESIGNER does not hold invoice:view

    brand_notifs = await _notifications_for(
        ctx.brand_manager_id, NotificationEventType.INVOICE_PAYMENT_RECEIVED.value
    )
    assert brand_notifs == []  # never the brand for this event


async def test_partial_payment_does_not_emit_payment_received(ctx: Ctx) -> None:
    from app.models.enums import PaymentMethod

    invoice_id = await _make_invoice(
        ctx.agency_id,
        ctx.brand_id,
        due_date=TODAY + timedelta(days=10),
        status=ClientInvoiceStatus.SENT.value,
        total_cents=100_000,
    )

    async with AsyncSessionLocal() as session:
        svc = PaymentService(session)
        await svc.record_payment(
            ctx.agency_id,
            ctx.owner_id,
            PaymentCreate(
                brand_id=ctx.brand_id,
                invoice_id=invoice_id,
                amount_cents=50_000,
                currency="TRY",
                payment_method=PaymentMethod.BANK_TRANSFER.value,
                paid_at=datetime.now(UTC),
            ),
        )

    owner_notifs = await _notifications_for(
        ctx.owner_id, NotificationEventType.INVOICE_PAYMENT_RECEIVED.value
    )
    assert owner_notifs == []


# ── Domain-level idempotency: same real action emitted as two separate
# NotificationEvent rows must still yield exactly one WhatsApp delivery and
# one provider call (Part 6B-1 closing round). Each test also confirms that
# a genuinely *different* real occurrence on the same entity is never
# wrongly collapsed into the first one. ──────────────────────────────────


async def test_duplicate_brief_assigned_events_single_whatsapp_delivery(
    ctx: Ctx, approve_template
) -> None:
    await approve_template(
        "brief_assigned", content_sid="HXassigned", variable_schema={"1": "brief_title"}
    )
    fake = _FakeSentProvider()
    payload = {
        "brief_id": str(ctx.brief_id),
        "brief_title": "Assign Me",
        "assignee_id": str(ctx.designer_id),
        "summary": "assigned",
    }
    event_ids: list[uuid.UUID] = []
    with _patched_provider(fake):
        for _ in range(2):
            async with AsyncSessionLocal() as session:
                event = await NotificationDispatcher(session).emit(
                    NotificationEventType.BRIEF_ASSIGNED.value,
                    payload=payload,
                    agency_id=ctx.agency_id,
                    brand_id=ctx.brand_id,
                    actor_user_id=ctx.owner_id,
                    recipient_ids=[ctx.designer_id],
                )
                await session.commit()
            event_ids.append(event.id)

    assert len(set(event_ids)) == 2  # two distinct NotificationEvent rows
    wa = await _deliveries_for_events(event_ids, NotificationChannel.WHATSAPP.value)
    assert len(wa) == 1
    assert len(fake.calls) == 1


async def test_duplicate_comment_added_events_single_whatsapp_delivery(
    ctx: Ctx, approve_template
) -> None:
    await approve_template(
        "comment_added", content_sid="HXcomment", variable_schema={"1": "brief_title"}
    )
    fake = _FakeSentProvider()
    payload = {
        "brief_id": str(ctx.brief_id),
        "brief_title": "X",
        "comment_id": str(uuid.uuid4()),
        "comment_preview": "same comment, emitted twice",
    }
    event_ids: list[uuid.UUID] = []
    with _patched_provider(fake):
        for _ in range(2):
            async with AsyncSessionLocal() as session:
                event = await NotificationDispatcher(session).emit(
                    NotificationEventType.COMMENT_ADDED.value,
                    payload=payload,
                    agency_id=ctx.agency_id,
                    brand_id=ctx.brand_id,
                    actor_user_id=None,
                    recipient_ids=[ctx.owner_id],
                )
                await session.commit()
            event_ids.append(event.id)

    wa = await _deliveries_for_events(event_ids, NotificationChannel.WHATSAPP.value)
    assert len(wa) == 1
    assert len(fake.calls) == 1

    # A genuinely different comment on the same brief must still send.
    with _patched_provider(fake):
        async with AsyncSessionLocal() as session:
            other_event = await NotificationDispatcher(session).emit(
                NotificationEventType.COMMENT_ADDED.value,
                payload={**payload, "comment_id": str(uuid.uuid4())},
                agency_id=ctx.agency_id,
                brand_id=ctx.brand_id,
                actor_user_id=None,
                recipient_ids=[ctx.owner_id],
            )
            await session.commit()

    wa2 = await _deliveries_for_events([other_event.id], NotificationChannel.WHATSAPP.value)
    assert len(wa2) == 1
    assert wa2[0].status == NotificationDeliveryStatus.SENT.value
    assert len(fake.calls) == 2, "a genuinely different comment must send a new message"


async def test_duplicate_mention_created_events_single_whatsapp_delivery(
    ctx: Ctx, approve_template
) -> None:
    await approve_template(
        "mention_created", content_sid="HXmention", variable_schema={"1": "brief_title"}
    )
    fake = _FakeSentProvider()
    payload = {
        "brief_id": str(ctx.brief_id),
        "brief_title": "X",
        "comment_id": str(uuid.uuid4()),
        "actor_name": "Someone",
        "summary": "you were mentioned",
    }
    event_ids: list[uuid.UUID] = []
    with _patched_provider(fake):
        for _ in range(2):
            async with AsyncSessionLocal() as session:
                event = await NotificationDispatcher(session).emit(
                    NotificationEventType.MENTIONED_IN_COMMENT.value,
                    payload=payload,
                    agency_id=ctx.agency_id,
                    brand_id=ctx.brand_id,
                    actor_user_id=ctx.owner_id,
                    recipient_ids=[ctx.designer_id],
                )
                await session.commit()
            event_ids.append(event.id)

    wa = await _deliveries_for_events(event_ids, NotificationChannel.WHATSAPP.value)
    assert len(wa) == 1
    assert len(fake.calls) == 1


async def test_duplicate_deliverable_submitted_version_events(
    ctx: Ctx, approve_template
) -> None:
    """Same submission re-emitted -> one message; a *new* version (higher
    revision_count on the same deliverable_id, since deliverable_versioning
    mutates the same row in place rather than creating a new one) -> a new
    message."""
    await approve_template(
        "deliverable_submitted", content_sid="HXsubmit", variable_schema={"1": "brief_title"}
    )
    fake = _FakeSentProvider()
    deliverable_id = str(uuid.uuid4())
    v1_payload = {
        "brief_id": str(ctx.brief_id),
        "brief_title": "X",
        "deliverable_id": deliverable_id,
        "deliverable_title": "Post",
        "revision_count": 0,
        "summary": "submitted v1",
    }
    v1_event_ids: list[uuid.UUID] = []
    with _patched_provider(fake):
        for _ in range(2):
            async with AsyncSessionLocal() as session:
                event = await NotificationDispatcher(session).emit(
                    NotificationEventType.DELIVERABLE_SUBMITTED.value,
                    payload=v1_payload,
                    agency_id=ctx.agency_id,
                    brand_id=ctx.brand_id,
                    actor_user_id=None,
                    recipient_ids=[ctx.brand_manager_id],
                )
                await session.commit()
            v1_event_ids.append(event.id)

        wa_v1 = await _deliveries_for_events(v1_event_ids, NotificationChannel.WHATSAPP.value)
        assert len(wa_v1) == 1
        assert len(fake.calls) == 1

        # Resubmission after a revision request bumps revision_count on the
        # *same* deliverable_id — this is a genuinely new occurrence.
        async with AsyncSessionLocal() as session:
            v2_event = await NotificationDispatcher(session).emit(
                NotificationEventType.DELIVERABLE_SUBMITTED.value,
                payload={**v1_payload, "revision_count": 1, "summary": "submitted v2"},
                agency_id=ctx.agency_id,
                brand_id=ctx.brand_id,
                actor_user_id=None,
                recipient_ids=[ctx.brand_manager_id],
            )
            await session.commit()

    wa_v2 = await _deliveries_for_events([v2_event.id], NotificationChannel.WHATSAPP.value)
    assert len(wa_v2) == 1
    assert len(fake.calls) == 2, "a new deliverable version must send a new WhatsApp message"


async def test_duplicate_revision_requested_events(ctx: Ctx, approve_template) -> None:
    """Same revision-request re-emitted -> one message; a *second*, later
    revision request on the same deliverable (higher revision_count) -> a
    new message."""
    await approve_template(
        "revision_requested", content_sid="HXrevision", variable_schema={"1": "brief_title"}
    )
    fake = _FakeSentProvider()
    deliverable_id = str(uuid.uuid4())
    rev1_payload = {
        "brief_id": str(ctx.brief_id),
        "brief_title": "X",
        "deliverable_id": deliverable_id,
        "deliverable_title": "Post",
        "reason": "fix colors",
        "revision_count": 1,
        "summary": "revision 1 requested",
    }
    with _patched_provider(fake):
        rev1_event_ids: list[uuid.UUID] = []
        for _ in range(2):
            async with AsyncSessionLocal() as session:
                event = await NotificationDispatcher(session).emit(
                    NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value,
                    payload=rev1_payload,
                    agency_id=ctx.agency_id,
                    brand_id=ctx.brand_id,
                    actor_user_id=None,
                    recipient_ids=[ctx.owner_id],
                )
                await session.commit()
            rev1_event_ids.append(event.id)

        wa_rev1 = await _deliveries_for_events(rev1_event_ids, NotificationChannel.WHATSAPP.value)
        assert len(wa_rev1) == 1
        assert len(fake.calls) == 1

        async with AsyncSessionLocal() as session:
            rev2_event = await NotificationDispatcher(session).emit(
                NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value,
                payload={**rev1_payload, "revision_count": 2, "summary": "revision 2 requested"},
                agency_id=ctx.agency_id,
                brand_id=ctx.brand_id,
                actor_user_id=None,
                recipient_ids=[ctx.owner_id],
            )
            await session.commit()

    wa_rev2 = await _deliveries_for_events([rev2_event.id], NotificationChannel.WHATSAPP.value)
    assert len(wa_rev2) == 1
    assert len(fake.calls) == 2, "a second, distinct revision request must send a new message"


async def test_duplicate_invoice_payment_received_events_single_whatsapp_delivery(
    ctx: Ctx, approve_template
) -> None:
    await approve_template(
        "invoice_payment_received",
        content_sid="HXpayment",
        variable_schema={"1": "invoice_number"},
    )
    fake = _FakeSentProvider()
    payload = {
        "invoice_id": str(uuid.uuid4()),
        "invoice_number": "INV-0001",
        "payment_id": str(uuid.uuid4()),
        "amount_cents": 100_000,
        "currency": "TRY",
        "summary": "payment received",
    }
    event_ids: list[uuid.UUID] = []
    with _patched_provider(fake):
        for _ in range(2):
            async with AsyncSessionLocal() as session:
                event = await NotificationDispatcher(session).emit(
                    NotificationEventType.INVOICE_PAYMENT_RECEIVED.value,
                    payload=payload,
                    agency_id=ctx.agency_id,
                    brand_id=ctx.brand_id,
                    actor_user_id=None,
                    recipient_ids=[ctx.owner_id],
                )
                await session.commit()
            event_ids.append(event.id)

    wa = await _deliveries_for_events(event_ids, NotificationChannel.WHATSAPP.value)
    assert len(wa) == 1
    assert len(fake.calls) == 1


async def test_duplicate_brief_due_soon_same_day_single_whatsapp_delivery(
    ctx: Ctx, approve_template
) -> None:
    """Two due-soon reminders emitted for the same brief on the same UTC
    day collapse to one message; a reminder on the *next* allowed day is a
    new message."""
    await approve_template(
        "brief_due_soon", content_sid="HXduesoon", variable_schema={"1": "brief_title"}
    )
    fake = _FakeSentProvider()
    payload = {
        "brief_id": str(ctx.brief_id),
        "brief_title": "X",
        "deadline": TODAY.isoformat(),
        "summary": "due soon",
    }
    event_ids: list[uuid.UUID] = []
    with _patched_provider(fake):
        for _ in range(2):
            async with AsyncSessionLocal() as session:
                event = await NotificationDispatcher(session).emit(
                    NotificationEventType.CALENDAR_ITEM_DUE.value,
                    payload=payload,
                    agency_id=ctx.agency_id,
                    brand_id=ctx.brand_id,
                    actor_user_id=None,
                    recipient_ids=[ctx.owner_id],
                )
                await session.commit()
            event_ids.append(event.id)

        wa_today = await _deliveries_for_events(event_ids, NotificationChannel.WHATSAPP.value)
        assert len(wa_today) == 1
        assert len(fake.calls) == 1

        with patch(
            "app.services.notification_dedupe.utc_today",
            return_value=TODAY + timedelta(days=1),
        ):
            async with AsyncSessionLocal() as session:
                tomorrow_event = await NotificationDispatcher(session).emit(
                    NotificationEventType.CALENDAR_ITEM_DUE.value,
                    payload=payload,
                    agency_id=ctx.agency_id,
                    brand_id=ctx.brand_id,
                    actor_user_id=None,
                    recipient_ids=[ctx.owner_id],
                )
                await session.commit()

    wa_tomorrow = await _deliveries_for_events(
        [tomorrow_event.id], NotificationChannel.WHATSAPP.value
    )
    assert len(wa_tomorrow) == 1
    assert len(fake.calls) == 2, "the next allowed reminder day must send a new message"


async def test_duplicate_invoice_overdue_same_day_single_whatsapp_delivery(
    ctx: Ctx, approve_template
) -> None:
    await approve_template(
        "invoice_overdue", content_sid="HXoverdue", variable_schema={"1": "invoice_number"}
    )
    fake = _FakeSentProvider()
    payload = {
        "invoice_id": str(uuid.uuid4()),
        "invoice_number": "INV-0002",
        "due_date": (TODAY - timedelta(days=3)).isoformat(),
        "days_overdue": 3,
        "summary": "overdue",
    }
    event_ids: list[uuid.UUID] = []
    with _patched_provider(fake):
        for _ in range(2):
            async with AsyncSessionLocal() as session:
                event = await NotificationDispatcher(session).emit(
                    NotificationEventType.INVOICE_OVERDUE.value,
                    payload=payload,
                    agency_id=ctx.agency_id,
                    brand_id=ctx.brand_id,
                    actor_user_id=None,
                    recipient_ids=[ctx.owner_id],
                )
                await session.commit()
            event_ids.append(event.id)

    wa = await _deliveries_for_events(event_ids, NotificationChannel.WHATSAPP.value)
    assert len(wa) == 1
    assert len(fake.calls) == 1


async def test_concurrent_workers_racing_same_domain_occurrence_single_delivery(
    ctx: Ctx, approve_template
) -> None:
    """Two separate NotificationEvent rows for the *same* real comment,
    dispatched concurrently from two independent sessions (simulating two
    workers racing on the same domain occurrence) — the DB-unique
    idempotency_key (via NotificationDeliveryRepository.reserve()) must let
    only one of them proceed to the provider."""
    await approve_template(
        "comment_added", content_sid="HXrace", variable_schema={"1": "brief_title"}
    )
    fake = _FakeSentProvider()
    comment_id = str(uuid.uuid4())
    payload = {
        "brief_id": str(ctx.brief_id),
        "brief_title": "Race",
        "comment_id": comment_id,
        "comment_preview": "racing comment",
    }

    async with AsyncSessionLocal() as s1, AsyncSessionLocal() as s2:
        event1 = await NotificationEventRepository(s1).create(
            event_type=NotificationEventType.COMMENT_ADDED.value,
            payload=payload,
            agency_id=ctx.agency_id,
            brand_id=ctx.brand_id,
            actor_user_id=None,
        )
        await s1.commit()
        event2 = await NotificationEventRepository(s2).create(
            event_type=NotificationEventType.COMMENT_ADDED.value,
            payload=payload,
            agency_id=ctx.agency_id,
            brand_id=ctx.brand_id,
            actor_user_id=None,
        )
        await s2.commit()

    async def _run(event) -> None:
        async with AsyncSessionLocal() as session:
            dispatcher = NotificationDispatcher(session)
            user = await session.get(User, ctx.owner_id)
            pref = await NotificationPreferenceRepository(session).get_or_create(ctx.owner_id)
            await dispatcher._dispatch_whatsapp(
                event=event,
                user=user,
                pref=pref,
                demo_sandbox=False,
                wa_provider=fake,
                actor_user=None,
            )
            await session.commit()

    with _patched_provider(fake):
        await asyncio.gather(_run(event1), _run(event2))

    wa = await _deliveries_for_events(
        [event1.id, event2.id], NotificationChannel.WHATSAPP.value
    )
    assert len(wa) == 1, "two concurrent dispatches for the same occurrence must yield one row"
    assert len(fake.calls) == 1, "the provider must be called at most once, never twice"

"""Backend tests for WhatsApp per-event preferences, consent, and the
Owner/Admin management center (Part 6B-2).

Covers: consent create/opt-out (self-scoped only), per-event WhatsApp toggle
persistence and duplicate-row prevention, role-based event visibility,
template-readiness reflection, dispatcher enforcement of the per-event
toggle, Owner/Admin summary/template-matrix/delivery-history endpoints
(RBAC + tenant isolation + pagination + secret exclusion + phone masking),
and demo-tenant restrictions. No real Twilio call is ever made.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.enums import (
    AgencyMemberRole,
    AgencyMemberStatus,
    BrandMemberRole,
    BrandMemberStatus,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
    UserType,
    WhatsAppTemplateStatus,
)
from app.models.notification import (
    NotificationDelivery,
    NotificationEventPreference,
    NotificationPreference,
)
from app.models.user import User
from app.repositories.notification import (
    NotificationEventPreferenceRepository,
    NotificationPreferenceRepository,
)
from app.repositories.whatsapp_template import WhatsAppTemplateRepository
from app.services.notification_dispatcher import NotificationDispatcher

pytestmark = pytest.mark.asyncio


def _agency_headers(token: str, agency_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Agency-ID": str(agency_id)}


def _brand_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token(user_id: uuid.UUID) -> str:
    return create_access_token(str(user_id))


@dataclass
class PrefCtx:
    agency_id: uuid.UUID
    brand_id: uuid.UUID
    owner_id: uuid.UUID
    owner_token: str
    designer_id: uuid.UUID
    designer_token: str
    brand_manager_id: uuid.UUID
    brand_manager_token: str
    brand_viewer_id: uuid.UUID
    brand_viewer_token: str


async def _make_user(session, label: str, *, user_type: str = UserType.AGENCY_USER.value) -> User:
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


async def _seed(label: str, *, is_demo: bool = False) -> PrefCtx:
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
        await session.commit()

        return PrefCtx(
            agency_id=agency.id,
            brand_id=brand.id,
            owner_id=owner.id,
            owner_token=_token(owner.id),
            designer_id=designer.id,
            designer_token=_token(designer.id),
            brand_manager_id=brand_manager.id,
            brand_manager_token=_token(brand_manager.id),
            brand_viewer_id=brand_viewer.id,
            brand_viewer_token=_token(brand_viewer.id),
        )


async def _cleanup(pctx: PrefCtx) -> None:
    async with AsyncSessionLocal() as session:
        agency = await session.get(Agency, pctx.agency_id)
        if agency is not None:
            await session.delete(agency)
        brand = await session.get(Brand, pctx.brand_id)
        if brand is not None:
            await session.delete(brand)
        await session.commit()
        for uid in (pctx.owner_id, pctx.designer_id, pctx.brand_manager_id, pctx.brand_viewer_id):
            user = await session.get(User, uid)
            if user is not None:
                await session.delete(user)
        await session.commit()


@pytest.fixture
async def pctx():
    c = await _seed("Pref")
    try:
        yield c
    finally:
        await _cleanup(c)


@pytest.fixture
async def demo_pctx():
    c = await _seed("DemoPref", is_demo=True)
    try:
        yield c
    finally:
        await _cleanup(c)


@pytest.fixture
async def approve_template():
    """Approve a seeded draft template for the test, restore to draft after —
    mirrors test_whatsapp_event_dispatch.py's fixture of the same name since
    the 16 rows are shared, migration-seeded singletons keyed by `code`."""
    approved: list[str] = []

    async def _approve(code: str) -> None:
        async with AsyncSessionLocal() as session:
            repo = WhatsAppTemplateRepository(session)
            tpl = await repo.get_by_code(code)
            assert tpl is not None
            tpl.status = WhatsAppTemplateStatus.APPROVED.value
            tpl.content_sid = "HXfake" + uuid.uuid4().hex[:8]
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
                session.add(tpl)
        await session.commit()


async def _set_phone(user_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        user.phone_number = "+90555" + str(uuid.uuid4().int)[:7]
        session.add(user)
        await session.commit()


async def _make_whatsapp_ready(user_id: uuid.UUID) -> None:
    await _set_phone(user_id)
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        user.whatsapp_opt_in = True
        session.add(user)
        pref_repo = NotificationPreferenceRepository(session)
        pref = await pref_repo.get_or_create(user_id)
        await pref_repo.update(pref, email_enabled=True, whatsapp_enabled=True, in_app_enabled=True)
        await session.commit()


# ── Consent: self-scoped only ────────────────────────────────────────────────


async def test_consent_opt_in_sets_master_toggle_and_provenance(client, pctx: PrefCtx) -> None:
    await _set_phone(pctx.owner_id)
    resp = await client.post(
        "/api/v1/notifications/whatsapp/consent",
        json={"opt_in": True},
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["master_enabled"] is True
    assert body["consent"]["whatsapp_opt_in"] is True
    assert body["consent"]["whatsapp_opt_in_at"] is not None
    assert body["consent"]["whatsapp_consent_source"] == "in_app_toggle"
    assert body["consent"]["whatsapp_consent_version"] is not None


async def test_consent_opt_out_disables_master_toggle(client, pctx: PrefCtx) -> None:
    await _set_phone(pctx.owner_id)
    await client.post(
        "/api/v1/notifications/whatsapp/consent",
        json={"opt_in": True},
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )
    resp = await client.post(
        "/api/v1/notifications/whatsapp/consent",
        json={"opt_in": False},
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["master_enabled"] is False
    assert body["consent"]["whatsapp_opt_in"] is False
    assert body["consent"]["whatsapp_opt_out_at"] is not None


async def test_owner_cannot_set_consent_for_another_user(client, pctx: PrefCtx) -> None:
    """The consent endpoint has no target-user field at all — it always acts
    on the JWT-authenticated caller. Confirm the Owner opting in doesn't
    touch the Designer's own consent state."""
    await _set_phone(pctx.owner_id)
    await client.post(
        "/api/v1/notifications/whatsapp/consent",
        json={"opt_in": True},
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )

    designer_status = await client.get(
        "/api/v1/notifications/whatsapp/status",
        headers=_agency_headers(pctx.designer_token, pctx.agency_id),
    )
    assert designer_status.status_code == 200
    assert designer_status.json()["consent"]["whatsapp_opt_in"] is False


async def test_phone_masking_never_returns_raw_number(client, pctx: PrefCtx) -> None:
    raw_phone = "+905551234567"
    async with AsyncSessionLocal() as session:
        user = await session.get(User, pctx.owner_id)
        user.phone_number = raw_phone
        session.add(user)
        await session.commit()

    resp = await client.get(
        "/api/v1/notifications/whatsapp/status",
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )
    assert resp.status_code == 200
    masked = resp.json()["phone"]["phone_masked"]
    assert masked != raw_phone
    assert raw_phone not in resp.text


# ── Per-event preference: persistence, duplicate prevention, role filtering ──


async def test_event_preference_update_persists_and_is_idempotent(client, pctx: PrefCtx) -> None:
    await _set_phone(pctx.owner_id)
    await client.post(
        "/api/v1/notifications/whatsapp/consent",
        json={"opt_in": True},
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )

    event_type = NotificationEventType.BRIEF_CREATED.value
    for enabled in (False, True, False):
        resp = await client.patch(
            f"/api/v1/notifications/whatsapp/event-preferences/{event_type}",
            json={"whatsapp_enabled": enabled},
            headers=_agency_headers(pctx.owner_token, pctx.agency_id),
        )
        assert resp.status_code == 200
        assert resp.json()["whatsapp_enabled"] is enabled

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NotificationEventPreference).where(
                NotificationEventPreference.user_id == pctx.owner_id,
                NotificationEventPreference.event_type == event_type,
            )
        )
        rows = result.scalars().all()
    assert len(rows) == 1  # duplicate-row prevention via ON CONFLICT DO UPDATE
    assert rows[0].whatsapp_enabled is False
    assert rows[0].updated_by_user_id == pctx.owner_id


async def test_event_preference_forbidden_for_role_without_permission(
    client, pctx: PrefCtx
) -> None:
    """brief.submitted_for_approval requires BRIEF_APPROVE — brand_viewer
    doesn't hold it, so the toggle must be rejected server-side even via a
    direct API call, not just hidden client-side."""
    resp = await client.patch(
        f"/api/v1/notifications/whatsapp/event-preferences/{NotificationEventType.BRIEF_SUBMITTED.value}",
        json={"whatsapp_enabled": False},
        headers=_brand_headers(pctx.brand_viewer_token),
    )
    assert resp.status_code == 403


async def test_event_preference_allowed_for_role_with_permission(client, pctx: PrefCtx) -> None:
    resp = await client.patch(
        f"/api/v1/notifications/whatsapp/event-preferences/{NotificationEventType.BRIEF_SUBMITTED.value}",
        json={"whatsapp_enabled": False},
        headers=_brand_headers(pctx.brand_manager_token),
    )
    assert resp.status_code == 200


async def test_brand_user_does_not_see_finance_or_internal_events(client, pctx: PrefCtx) -> None:
    resp = await client.get(
        "/api/v1/notifications/whatsapp/status", headers=_brand_headers(pctx.brand_manager_token)
    )
    assert resp.status_code == 200
    event_types = {e["event_type"] for e in resp.json()["events"]}
    # invoice.overdue / invoice.payment_received are agency-only in the catalog.
    assert NotificationEventType.INVOICE_OVERDUE.value not in event_types
    assert NotificationEventType.INVOICE_PAYMENT_RECEIVED.value not in event_types


async def test_concurrent_preference_reads_create_one_row(client, pctx: PrefCtx) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(NotificationPreference).where(
                NotificationPreference.user_id == pctx.brand_manager_id
            )
        )
        await session.commit()

    headers = _brand_headers(pctx.brand_manager_token)
    preferences_response, whatsapp_response = await asyncio.gather(
        client.get("/api/v1/notifications/preferences", headers=headers),
        client.get("/api/v1/notifications/whatsapp/status", headers=headers),
    )

    assert preferences_response.status_code == 200
    assert whatsapp_response.status_code == 200

    async with AsyncSessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(NotificationPreference).where(
                        NotificationPreference.user_id == pctx.brand_manager_id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1


async def test_viewer_cannot_update_another_users_preference(client, pctx: PrefCtx) -> None:
    """There is no id in the update path — it always targets the caller.
    Confirm the Designer toggling an event never touches the Owner's row."""
    event_type = NotificationEventType.BRIEF_CREATED.value
    resp = await client.patch(
        f"/api/v1/notifications/whatsapp/event-preferences/{event_type}",
        json={"whatsapp_enabled": False},
        headers=_agency_headers(pctx.designer_token, pctx.agency_id),
    )
    assert resp.status_code == 200

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NotificationEventPreference).where(
                NotificationEventPreference.user_id == pctx.owner_id,
                NotificationEventPreference.event_type == event_type,
            )
        )
        assert result.scalar_one_or_none() is None


# ── Template readiness ───────────────────────────────────────────────────────


async def test_missing_template_state(client, pctx: PrefCtx) -> None:
    resp = await client.get(
        "/api/v1/notifications/whatsapp/status",
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )
    assert resp.status_code == 200
    events = {e["event_type"]: e for e in resp.json()["events"]}
    assert events[NotificationEventType.BRIEF_CREATED.value]["template_ready"] is False


async def test_approved_template_state(client, pctx: PrefCtx, approve_template) -> None:
    await approve_template("brief_created")
    resp = await client.get(
        "/api/v1/notifications/whatsapp/status",
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )
    assert resp.status_code == 200
    events = {e["event_type"]: e for e in resp.json()["events"]}
    assert events[NotificationEventType.BRIEF_CREATED.value]["template_ready"] is True


# ── Dispatcher enforcement of the per-event toggle ──────────────────────────


async def test_event_toggle_disabled_skips_delivery(
    client, pctx: PrefCtx, approve_template
) -> None:
    await approve_template("brief_created")
    await _make_whatsapp_ready(pctx.owner_id)

    async with AsyncSessionLocal() as session:
        event_pref_repo = NotificationEventPreferenceRepository(session)
        await event_pref_repo.upsert_whatsapp_toggle(
            pctx.owner_id, NotificationEventType.BRIEF_CREATED.value, False, pctx.owner_id
        )
        await session.commit()

        event = await NotificationDispatcher(session).emit(
            NotificationEventType.BRIEF_CREATED.value,
            payload={"brief_id": str(uuid.uuid4()), "brief_title": "X"},
            agency_id=pctx.agency_id,
            brand_id=pctx.brand_id,
            actor_user_id=None,
            recipient_ids=[pctx.owner_id],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NotificationDelivery).where(
                NotificationDelivery.event_id == event.id,
                NotificationDelivery.channel == NotificationChannel.WHATSAPP.value,
            )
        )
        deliveries = result.scalars().all()
    assert len(deliveries) == 1
    assert deliveries[0].status == NotificationDeliveryStatus.SKIPPED_EVENT_DISABLED.value
    assert deliveries[0].recipient_user_id == pctx.owner_id


async def test_event_toggle_enabled_but_master_off_still_skipped(
    client, pctx: PrefCtx, approve_template
) -> None:
    """A per-event toggle can only narrow delivery further — it never
    overrides the master toggle/consent gate."""
    await approve_template("brief_created")
    await _set_phone(pctx.owner_id)  # consent/master left at their default-off state

    async with AsyncSessionLocal() as session:
        event_pref_repo = NotificationEventPreferenceRepository(session)
        await event_pref_repo.upsert_whatsapp_toggle(
            pctx.owner_id, NotificationEventType.BRIEF_CREATED.value, True, pctx.owner_id
        )
        await session.commit()

        event = await NotificationDispatcher(session).emit(
            NotificationEventType.BRIEF_CREATED.value,
            payload={"brief_id": str(uuid.uuid4()), "brief_title": "X"},
            agency_id=pctx.agency_id,
            brand_id=pctx.brand_id,
            actor_user_id=None,
            recipient_ids=[pctx.owner_id],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NotificationDelivery).where(
                NotificationDelivery.event_id == event.id,
                NotificationDelivery.channel == NotificationChannel.WHATSAPP.value,
            )
        )
        deliveries = result.scalars().all()
    assert deliveries[0].status == NotificationDeliveryStatus.SKIPPED_NO_CONSENT.value


# ── Owner/Admin management center: RBAC + tenant isolation ─────────────────


async def test_owner_summary_requires_manage_notifications_permission(
    client, pctx: PrefCtx
) -> None:
    resp = await client.get(
        "/api/v1/notifications/whatsapp/summary",
        headers=_agency_headers(pctx.designer_token, pctx.agency_id),
    )
    assert resp.status_code == 403


async def test_owner_summary_accessible_to_owner(client, pctx: PrefCtx) -> None:
    resp = await client.get(
        "/api/v1/notifications/whatsapp/summary",
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "connection_status" in body
    assert "demo_tenant" in body


async def test_owner_summary_excludes_secrets(client, pctx: PrefCtx) -> None:
    resp = await client.get(
        "/api/v1/notifications/whatsapp/summary",
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )
    assert resp.status_code == 200
    text_lower = resp.text.lower()
    for forbidden in ("auth_token", "account_sid", "content_sid", "password"):
        assert forbidden not in text_lower


async def test_template_matrix_never_exposes_content_sid_value(
    client, pctx: PrefCtx, approve_template
) -> None:
    await approve_template("brief_created")
    resp = await client.get(
        "/api/v1/notifications/whatsapp/template-matrix",
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )
    assert resp.status_code == 200
    stripped = resp.text.lower().replace("has_content_sid", "")
    assert "content_sid" not in stripped


async def test_template_preview_uses_placeholder_data_only(client, pctx: PrefCtx) -> None:
    resp = await client.get(
        f"/api/v1/notifications/whatsapp/template-preview/{NotificationEventType.BRIEF_CREATED.value}",
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "Ayşe" in body["sample_message"] or "Yeni Kampanya" in body["sample_message"]
    assert body["status"] == "preview_only"


async def test_demo_tenant_test_send_never_sends_real_message(client, demo_pctx: PrefCtx) -> None:
    await _make_whatsapp_ready(demo_pctx.owner_id)

    resp = await client.post(
        "/api/v1/notifications/whatsapp/test",
        headers=_agency_headers(demo_pctx.owner_token, demo_pctx.agency_id),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == NotificationDeliveryStatus.SKIPPED_DEMO_TENANT.value


async def test_test_send_available_to_non_owner_agency_role(client, pctx: PrefCtx) -> None:
    """Part 6B-2 widens self-service test-send beyond Owner/Admin — any
    active agency member may trigger it for their own number."""
    resp = await client.post(
        "/api/v1/notifications/whatsapp/test",
        headers=_agency_headers(pctx.designer_token, pctx.agency_id),
    )
    assert resp.status_code == 200  # gated by consent/phone inside the service, not by role


async def test_delivery_history_tenant_isolation(client, pctx: PrefCtx, approve_template) -> None:
    other = await _seed("PrefOther")
    try:
        await approve_template("brief_created")
        await _make_whatsapp_ready(pctx.owner_id)

        async with AsyncSessionLocal() as session:
            await NotificationDispatcher(session).emit(
                NotificationEventType.BRIEF_CREATED.value,
                payload={"brief_id": str(uuid.uuid4()), "brief_title": "Isolation Test"},
                agency_id=pctx.agency_id,
                brand_id=pctx.brand_id,
                actor_user_id=None,
                recipient_ids=[pctx.owner_id],
            )
            await session.commit()

        other_resp = await client.get(
            "/api/v1/notifications/whatsapp/deliveries",
            headers=_agency_headers(other.owner_token, other.agency_id),
        )
        assert other_resp.status_code == 200
        assert other_resp.json()["total"] == 0

        own_resp = await client.get(
            "/api/v1/notifications/whatsapp/deliveries",
            headers=_agency_headers(pctx.owner_token, pctx.agency_id),
        )
        assert own_resp.status_code == 200
        assert own_resp.json()["total"] >= 1
    finally:
        await _cleanup(other)


async def test_delivery_history_pagination(client, pctx: PrefCtx, approve_template) -> None:
    await approve_template("brief_created")
    await _make_whatsapp_ready(pctx.owner_id)

    async with AsyncSessionLocal() as session:
        for i in range(3):
            await NotificationDispatcher(session).emit(
                NotificationEventType.BRIEF_CREATED.value,
                payload={"brief_id": str(uuid.uuid4()), "brief_title": f"Page Test {i}"},
                agency_id=pctx.agency_id,
                brand_id=pctx.brand_id,
                actor_user_id=None,
                recipient_ids=[pctx.owner_id],
            )
        await session.commit()

    page1 = await client.get(
        "/api/v1/notifications/whatsapp/deliveries?limit=2&offset=0",
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert body1["total"] >= 3
    assert len(body1["items"]) == 2

    page2 = await client.get(
        "/api/v1/notifications/whatsapp/deliveries?limit=2&offset=2",
        headers=_agency_headers(pctx.owner_token, pctx.agency_id),
    )
    assert page2.status_code == 200
    assert len(page2.json()["items"]) >= 1

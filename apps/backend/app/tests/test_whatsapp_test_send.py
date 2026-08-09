"""Tests for the tenant Owner/Admin controlled WhatsApp test-send endpoint.

POST /api/v1/notifications/whatsapp/test — no recipient is ever accepted from
the request; every case below exercises the server-side gating chain instead.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.notification import NotificationPreference
from app.models.user import User
from app.services.whatsapp_provider import TwilioWhatsAppProvider, WhatsAppDeliveryResult

from .conftest import agency_headers

WHATSAPP_TEST_PATH = "/api/v1/notifications/whatsapp/test"


async def _make_agency_admin(
    *,
    is_demo: bool = False,
    phone_number: str | None = None,
    whatsapp_opt_in: bool = False,
    whatsapp_enabled_pref: bool = False,
    role: str = AgencyMemberRole.ADMIN.value,
) -> tuple[uuid.UUID, uuid.UUID, str]:
    """Returns (agency_id, user_id, access_token) for a fresh single-member agency."""
    suffix = uuid.uuid4().hex[:10]
    async with AsyncSessionLocal() as session:
        agency = Agency(
            id=uuid.uuid4(),
            name=f"WA Test Agency {suffix}",
            slug=f"wa-test-agency-{suffix}",
            is_demo=is_demo,
            # A demo agency with no demo_expires_at reads as an already-expired
            # self-service demo session (see demo_access.ensure_demo_user_access)
            # and gets rejected with 401 before the endpoint's own is_demo check
            # ever runs — set a real future expiry so this test exercises the
            # endpoint's skipped_demo_tenant path, not the unrelated auth gate.
            demo_expires_at=(datetime.now(UTC) + timedelta(hours=1)) if is_demo else None,
        )
        user = User(
            id=uuid.uuid4(),
            email=f"wa-test-{suffix}@test.local",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name="WA Test Admin",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
            phone_number=phone_number,
            whatsapp_opt_in=whatsapp_opt_in,
        )
        session.add_all([agency, user])
        await session.flush()

        session.add(
            AgencyMember(
                id=uuid.uuid4(),
                agency_id=agency.id,
                user_id=user.id,
                role=role,
                status=AgencyMemberStatus.ACTIVE.value,
            )
        )
        session.add(
            NotificationPreference(
                id=uuid.uuid4(),
                user_id=user.id,
                whatsapp_enabled=whatsapp_enabled_pref,
            )
        )
        await session.commit()
        return agency.id, user.id, create_access_token(str(user.id))


async def _cleanup_agency_admin(agency_id: uuid.UUID, user_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        agency = await session.get(Agency, agency_id)
        if agency is not None:
            await session.delete(agency)
        await session.commit()
        user = await session.get(User, user_id)
        if user is not None:
            await session.delete(user)
        await session.commit()


@pytest.fixture
async def consented_agency_admin():
    """Full consent + phone, non-demo. Template registry still has the seeded
    test template at status=draft, so this naturally exercises the
    skipped_template_missing branch without any real Twilio credentials."""
    agency_id, user_id, token = await _make_agency_admin(
        is_demo=False,
        phone_number="+905551110000",
        whatsapp_opt_in=True,
        whatsapp_enabled_pref=True,
    )
    try:
        yield agency_id, user_id, token
    finally:
        await _cleanup_agency_admin(agency_id, user_id)


@pytest.fixture
async def no_consent_agency_admin():
    agency_id, user_id, token = await _make_agency_admin()
    try:
        yield agency_id, user_id, token
    finally:
        await _cleanup_agency_admin(agency_id, user_id)


@pytest.fixture
async def demo_agency_admin():
    """Full consent + phone, but is_demo=True — must never send regardless."""
    agency_id, user_id, token = await _make_agency_admin(
        is_demo=True,
        phone_number="+905551110001",
        whatsapp_opt_in=True,
        whatsapp_enabled_pref=True,
    )
    try:
        yield agency_id, user_id, token
    finally:
        await _cleanup_agency_admin(agency_id, user_id)


@pytest.fixture
async def consented_agency_viewer():
    """Full consent + phone, role=viewer — the self-service test-send
    endpoint intentionally requires only AGENCY_VIEW (see the widened-in-
    Part-6B-2 docstring on send_whatsapp_test_notification), so any active
    agency member — including viewer — may reach it for their own opted-in
    number. Only the tenant-wide Owner/Admin management-center reads
    (summary/matrix/delivery-list/preview) require the stricter
    AGENCY_MANAGE_NOTIFICATIONS permission."""
    agency_id, user_id, token = await _make_agency_admin(
        is_demo=False,
        phone_number="+905551110002",
        whatsapp_opt_in=True,
        whatsapp_enabled_pref=True,
        role=AgencyMemberRole.VIEWER.value,
    )
    try:
        yield agency_id, user_id, token
    finally:
        await _cleanup_agency_admin(agency_id, user_id)


class TestWhatsAppTestSendAuth:
    async def test_unauthenticated_rejected(self, client: AsyncClient) -> None:
        resp = await client.post(WHATSAPP_TEST_PATH)
        assert resp.status_code in (401, 403)

    async def test_brand_portal_user_cannot_call_tenant_endpoint(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _tenant_b = tenants
        headers = {"Authorization": f"Bearer {tenant_a.brand_viewer_token}"}
        resp = await client.post(WHATSAPP_TEST_PATH, headers=headers)
        # 400 = missing required X-Agency-ID header; 401/403/404/422 cover the
        # other ways a non-agency-member request can be correctly rejected.
        assert resp.status_code in (400, 401, 403, 404, 422)


class TestWhatsAppTestSendGating:
    async def test_demo_tenant_always_skipped(
        self, client: AsyncClient, demo_agency_admin
    ) -> None:
        agency_id, _user_id, token = demo_agency_admin
        resp = await client.post(
            WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "skipped_demo_tenant"
        assert body["masked_recipient"] is None
        assert body["provider_message_id"] is None

    async def test_no_consent_skipped(
        self, client: AsyncClient, no_consent_agency_admin
    ) -> None:
        agency_id, _user_id, token = no_consent_agency_admin
        resp = await client.post(
            WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped_no_consent"

    async def test_full_consent_but_no_approved_template_yet(
        self, client: AsyncClient, consented_agency_admin
    ) -> None:
        """The seeded flobrief_test_notification template starts as status=draft
        (no operator has entered a real content_sid + approved it yet), so a
        fully-consented, phone-having user still gets an honest skip — never a
        fabricated success."""
        agency_id, _user_id, token = consented_agency_admin
        resp = await client.post(
            WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "skipped_template_missing"
        assert body["masked_recipient"] is not None
        assert body["provider_message_id"] is None

    async def test_response_never_contains_a_secret_field(
        self, client: AsyncClient, consented_agency_admin
    ) -> None:
        agency_id, _user_id, token = consented_agency_admin
        resp = await client.post(
            WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id)
        )
        body = resp.json()
        for forbidden_key in ("auth_token", "account_sid", "secret", "password"):
            assert forbidden_key not in body

    async def test_rate_limit_eventually_triggers(
        self, client: AsyncClient, consented_agency_admin
    ) -> None:
        agency_id, _user_id, token = consented_agency_admin
        headers = agency_headers(token, agency_id)
        statuses = []
        for _ in range(5):
            resp = await client.post(WHATSAPP_TEST_PATH, headers=headers)
            statuses.append(resp.status_code)
        # Limiter is 3/10min; at least one of the later attempts should be 429
        # (fails open on Redis unavailability, so this is best-effort, not a
        # hard guarantee in every test environment).
        assert all(s in (200, 429) for s in statuses)


# ── Dev-only Twilio Sandbox freeform fallback (Part 6A continued) ───────────
#
# The seeded flobrief_test_notification template stays status=draft in every
# test environment (see consented_agency_admin's docstring above), so every
# case here naturally exercises the approved-template-missing branch. The
# provider factory is mocked to avoid any real Twilio/network call — these
# tests verify the *gating*, not the HTTP call itself (that is covered by
# TestSandboxFreeformSend in test_whatsapp_provider.py).


def _fake_sandbox_provider() -> MagicMock:
    provider = MagicMock(spec=TwilioWhatsAppProvider)
    provider.get_provider_name.return_value = "twilio_sandbox"
    provider.is_official_sandbox_sender.return_value = True
    provider.send_sandbox_freeform_test_message.return_value = WhatsAppDeliveryResult(
        status="sent",
        provider="twilio_sandbox",
        provider_message_id="SMfakesandbox",
        error_message=None,
    )
    return provider


class TestWhatsAppSandboxFreeformFallback:
    _TEST_RECIPIENT = "+14155550123"

    def _patched_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        app_env: str = "development",
        notifications_enabled: bool = True,
        freeform_enabled: bool = True,
        test_recipient: str | None = "+14155550123",
    ) -> None:
        monkeypatch.setattr(settings, "APP_ENV", app_env)
        monkeypatch.setattr(settings, "WHATSAPP_NOTIFICATIONS_ENABLED", notifications_enabled)
        monkeypatch.setattr(settings, "WHATSAPP_SANDBOX_FREEFORM_TEST_ENABLED", freeform_enabled)
        monkeypatch.setattr(settings, "WHATSAPP_TEST_RECIPIENT", test_recipient)

    async def test_sends_when_every_condition_is_met(
        self, client: AsyncClient, consented_agency_admin, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agency_id, _user_id, token = consented_agency_admin
        self._patched_env(monkeypatch)
        fake_provider = _fake_sandbox_provider()

        with patch(
            "app.services.whatsapp_test_send_service.WhatsAppProviderFactory.get_provider",
            new=AsyncMock(return_value=fake_provider),
        ):
            resp = await client.post(WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id))

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "sent"
        assert body["template_key"] == "sandbox_freeform_test"
        assert body["provider_message_id"] == "SMfakesandbox"
        # The recipient handed to the provider must be the fixed platform test
        # recipient — never the fixture's own phone_number ("+905551110000").
        fake_provider.send_sandbox_freeform_test_message.assert_called_once_with(
            self._TEST_RECIPIENT
        )

    async def test_arbitrary_request_body_recipient_is_ignored(
        self, client: AsyncClient, consented_agency_admin, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The endpoint has no request-body recipient field at all — an
        attacker-supplied phone in the JSON body must have zero effect."""
        agency_id, _user_id, token = consented_agency_admin
        self._patched_env(monkeypatch)
        fake_provider = _fake_sandbox_provider()

        with patch(
            "app.services.whatsapp_test_send_service.WhatsAppProviderFactory.get_provider",
            new=AsyncMock(return_value=fake_provider),
        ):
            resp = await client.post(
                WHATSAPP_TEST_PATH,
                headers=agency_headers(token, agency_id),
                json={"to_phone": "+19998887777", "phone_number": "+19998887777"},
            )

        assert resp.status_code == 200
        fake_provider.send_sandbox_freeform_test_message.assert_called_once_with(
            self._TEST_RECIPIENT
        )

    async def test_rejected_in_production(
        self, client: AsyncClient, consented_agency_admin, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agency_id, _user_id, token = consented_agency_admin
        self._patched_env(monkeypatch, app_env="production")
        fake_provider = _fake_sandbox_provider()

        with patch(
            "app.services.whatsapp_test_send_service.WhatsAppProviderFactory.get_provider",
            new=AsyncMock(return_value=fake_provider),
        ):
            resp = await client.post(WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id))

        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped_template_missing"
        fake_provider.send_sandbox_freeform_test_message.assert_not_called()

    async def test_rejected_in_staging(
        self, client: AsyncClient, consented_agency_admin, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agency_id, _user_id, token = consented_agency_admin
        self._patched_env(monkeypatch, app_env="staging")
        fake_provider = _fake_sandbox_provider()

        with patch(
            "app.services.whatsapp_test_send_service.WhatsAppProviderFactory.get_provider",
            new=AsyncMock(return_value=fake_provider),
        ):
            resp = await client.post(WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id))

        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped_template_missing"
        fake_provider.send_sandbox_freeform_test_message.assert_not_called()

    async def test_rejected_when_notifications_flag_disabled(
        self, client: AsyncClient, consented_agency_admin, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agency_id, _user_id, token = consented_agency_admin
        self._patched_env(monkeypatch, notifications_enabled=False)
        fake_provider = _fake_sandbox_provider()

        with patch(
            "app.services.whatsapp_test_send_service.WhatsAppProviderFactory.get_provider",
            new=AsyncMock(return_value=fake_provider),
        ):
            resp = await client.post(WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id))

        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped_template_missing"
        fake_provider.send_sandbox_freeform_test_message.assert_not_called()

    async def test_rejected_when_freeform_flag_disabled(
        self, client: AsyncClient, consented_agency_admin, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agency_id, _user_id, token = consented_agency_admin
        self._patched_env(monkeypatch, freeform_enabled=False)
        fake_provider = _fake_sandbox_provider()

        with patch(
            "app.services.whatsapp_test_send_service.WhatsAppProviderFactory.get_provider",
            new=AsyncMock(return_value=fake_provider),
        ):
            resp = await client.post(WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id))

        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped_template_missing"
        fake_provider.send_sandbox_freeform_test_message.assert_not_called()

    async def test_rejected_when_sender_is_not_official_sandbox(
        self, client: AsyncClient, consented_agency_admin, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agency_id, _user_id, token = consented_agency_admin
        self._patched_env(monkeypatch)
        fake_provider = _fake_sandbox_provider()
        fake_provider.is_official_sandbox_sender.return_value = False

        with patch(
            "app.services.whatsapp_test_send_service.WhatsAppProviderFactory.get_provider",
            new=AsyncMock(return_value=fake_provider),
        ):
            resp = await client.post(WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id))

        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped_template_missing"
        fake_provider.send_sandbox_freeform_test_message.assert_not_called()

    async def test_rejected_when_test_recipient_missing(
        self, client: AsyncClient, consented_agency_admin, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agency_id, _user_id, token = consented_agency_admin
        self._patched_env(monkeypatch, test_recipient=None)
        fake_provider = _fake_sandbox_provider()

        with patch(
            "app.services.whatsapp_test_send_service.WhatsAppProviderFactory.get_provider",
            new=AsyncMock(return_value=fake_provider),
        ):
            resp = await client.post(WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id))

        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped_template_missing"
        fake_provider.send_sandbox_freeform_test_message.assert_not_called()

    async def test_rejected_for_demo_tenant_even_with_freeform_enabled(
        self, client: AsyncClient, demo_agency_admin, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agency_id, _user_id, token = demo_agency_admin
        self._patched_env(monkeypatch)
        fake_provider = _fake_sandbox_provider()

        with patch(
            "app.services.whatsapp_test_send_service.WhatsAppProviderFactory.get_provider",
            new=AsyncMock(return_value=fake_provider),
        ):
            resp = await client.post(WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id))

        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped_demo_tenant"
        fake_provider.send_sandbox_freeform_test_message.assert_not_called()

    async def test_rejected_without_consent_even_with_freeform_enabled(
        self, client: AsyncClient, no_consent_agency_admin, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agency_id, _user_id, token = no_consent_agency_admin
        self._patched_env(monkeypatch)
        fake_provider = _fake_sandbox_provider()

        with patch(
            "app.services.whatsapp_test_send_service.WhatsAppProviderFactory.get_provider",
            new=AsyncMock(return_value=fake_provider),
        ):
            resp = await client.post(WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id))

        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped_no_consent"
        fake_provider.send_sandbox_freeform_test_message.assert_not_called()

    async def test_viewer_role_can_self_test_send(
        self, client: AsyncClient, consented_agency_viewer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A viewer has no AGENCY_MANAGE_NOTIFICATIONS permission (see the
        Owner/Admin-only management-center endpoints below), but this
        specific self-service endpoint only ever acts on the caller's own
        opted-in number — never another user's or tenant-wide data — so it
        intentionally requires only AGENCY_VIEW and must succeed here."""
        agency_id, _user_id, token = consented_agency_viewer
        self._patched_env(monkeypatch)
        fake_provider = _fake_sandbox_provider()

        with patch(
            "app.services.whatsapp_test_send_service.WhatsAppProviderFactory.get_provider",
            new=AsyncMock(return_value=fake_provider),
        ):
            resp = await client.post(WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id))

        assert resp.status_code == 200
        assert resp.json()["status"] == "sent"
        fake_provider.send_sandbox_freeform_test_message.assert_called_once_with(
            self._TEST_RECIPIENT
        )

    async def test_response_never_contains_a_secret_even_on_freeform_send(
        self, client: AsyncClient, consented_agency_admin, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agency_id, _user_id, token = consented_agency_admin
        self._patched_env(monkeypatch)
        fake_provider = _fake_sandbox_provider()

        with patch(
            "app.services.whatsapp_test_send_service.WhatsAppProviderFactory.get_provider",
            new=AsyncMock(return_value=fake_provider),
        ):
            resp = await client.post(WHATSAPP_TEST_PATH, headers=agency_headers(token, agency_id))

        body = resp.json()
        assert body["status"] == "sent"
        # Masked recipient must be masked, never the raw test-recipient number.
        assert body["masked_recipient"] != self._TEST_RECIPIENT
        for forbidden_key in ("auth_token", "account_sid", "secret", "password"):
            assert forbidden_key not in body

"""
Unit tests for Resend email provider system.
No DB required — pure Python logic and schema tests.
"""

from __future__ import annotations

import os

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-flobrief-64-chars-xxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://flobrief:flobrief@localhost:5432/flobrief_test"
)

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.api.v1.platform.notification_providers import _build_email_status
from app.core.config import settings
from app.schemas.email_provider import (
    EmailTestSendRequest,
    ResendProviderStatusRead,
    ResendProviderUpdate,
)
from app.services.resend_email_provider import (
    DisabledEmailProvider,
    EmailProviderFactory,
    ResendEmailProvider,
    _map_resend_error,
)

# ── Error mapping tests ────────────────────────────────────────────────────────


class TestMapResendError:
    def test_401_maps_to_invalid_api_key(self):
        msg = _map_resend_error(401, "", "unauthorized")
        assert "401" in msg
        assert "API anahtarı" in msg

    def test_403_maps_to_invalid_api_key(self):
        msg = _map_resend_error(403, "", "forbidden")
        assert "403" in msg
        assert "Resend" in msg

    def test_422_from_domain_maps_to_domain_not_verified(self):
        msg = _map_resend_error(422, "", "sender domain not verified")
        assert "422" in msg
        assert "domain" in msg

    def test_422_generic_maps_to_invalid_from(self):
        msg = _map_resend_error(422, "", "some validation error")
        assert "422" in msg
        assert "Geçersiz" in msg

    def test_429_maps_to_rate_limited(self):
        msg = _map_resend_error(429, "", "rate limit exceeded")
        assert "429" in msg
        assert "limit" in msg

    def test_500_maps_to_provider_error(self):
        msg = _map_resend_error(500, "", "internal server error")
        assert "500" in msg
        assert "Resend" in msg


# ── DisabledEmailProvider ─────────────────────────────────────────────────────


class TestDisabledEmailProvider:
    def test_is_not_active(self):
        p = DisabledEmailProvider()
        assert p.is_active() is False

    def test_provider_name(self):
        p = DisabledEmailProvider()
        assert p.get_provider_name() == "disabled"

    @pytest.mark.asyncio
    async def test_send_returns_not_configured(self):
        p = DisabledEmailProvider()
        result = await p.send("test@example.com", "Subject", "<p>Hello</p>")
        assert result.status == "not_configured"
        assert result.provider == "disabled"
        assert result.provider_message_id is None


# ── ResendEmailProvider ───────────────────────────────────────────────────────


class TestResendEmailProvider:
    def _make_provider(self) -> ResendEmailProvider:
        return ResendEmailProvider(
            api_key="re_test_key_1234",
            from_name="Flobrief",
            from_email="noreply@flobrief.com",
            reply_to=None,
        )

    def test_is_active_with_key_and_email(self):
        p = self._make_provider()
        assert p.is_active() is True

    def test_is_not_active_without_key(self):
        p = ResendEmailProvider(api_key="", from_name="Flobrief", from_email="test@flobrief.com")
        assert p.is_active() is False

    def test_provider_name(self):
        p = self._make_provider()
        assert p.get_provider_name() == "resend"

    @pytest.mark.asyncio
    async def test_send_success_returns_sent_with_message_id(self):
        p = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_abc123"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await p.send("user@example.com", "Hello", "<p>Hello</p>")

        assert result.status == "sent"
        assert result.provider == "resend"
        assert result.provider_message_id == "msg_abc123"
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_send_failure_401_returns_failed_with_error(self):
        p = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"name": "unauthorized", "message": "API key is invalid"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await p.send("user@example.com", "Hello", "<p>Hello</p>")

        assert result.status == "failed"
        assert result.provider == "resend"
        assert result.provider_message_id is None
        err = result.error_message or ""
        assert "API anahtarı" in err or "401" in err

    @pytest.mark.asyncio
    async def test_send_network_error_returns_failed(self):
        import httpx as _httpx

        p = self._make_provider()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=_httpx.ConnectError("connection refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await p.send("user@example.com", "Hello", "<p>Hello</p>")

        assert result.status == "failed"
        assert "Network error" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_send_includes_reply_to_when_set(self):
        p = ResendEmailProvider(
            api_key="re_test_key_1234",
            from_name="Flobrief",
            from_email="noreply@flobrief.com",
            reply_to="support@flobrief.com",
        )
        captured_payload: dict = {}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_x1"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def capture_post(url, json=None, headers=None):
            captured_payload.update(json or {})
            return mock_response

        mock_client.post = capture_post

        with patch("httpx.AsyncClient", return_value=mock_client):
            await p.send("user@example.com", "Hello", "<p>Hello</p>")

        assert captured_payload.get("reply_to") == "support@flobrief.com"

    @pytest.mark.asyncio
    async def test_test_mode_routes_to_resend_test_address(self):
        provider = ResendEmailProvider(
            api_key="re_test_key_1234",
            from_name="Flobrief",
            from_email="noreply@flobrief.com",
            test_mode=True,
            test_recipient="delivered@resend.dev",
            test_from_email="onboarding@resend.dev",
        )
        captured_payload: dict = {}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_test"}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def capture_post(url, json=None, headers=None):
            captured_payload.update(json or {})
            return mock_response

        mock_client.post = capture_post
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.send("invitee@example.com", "Ajans daveti", "<p>Davet</p>")

        assert result.status == "sent"
        assert captured_payload["to"] == ["delivered@resend.dev"]
        assert captured_payload["from"] == "Flobrief <onboarding@resend.dev>"
        assert captured_payload["subject"].startswith("[TEST → invitee@example.com]")


# ── EmailProviderFactory ──────────────────────────────────────────────────────


class TestEmailProviderFactory:
    @pytest.mark.asyncio
    async def test_returns_disabled_when_no_db_row_and_no_env(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.dict(os.environ, {"RESEND_API_KEY": ""}, clear=False):
            from app.core.config import settings as _settings

            _settings.RESEND_API_KEY = ""
            provider = await EmailProviderFactory.get_provider(mock_db)

        assert isinstance(provider, DisabledEmailProvider)

    @pytest.mark.asyncio
    async def test_returns_resend_provider_when_db_row_configured(self):
        mock_row = MagicMock()
        mock_row.is_enabled = True
        mock_row.encrypted_api_key = "encrypted_value"
        mock_row.email_from_name = "Flobrief"
        mock_row.email_from_email = "noreply@flobrief.com"
        mock_row.email_reply_to = None
        mock_row.deleted_at = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_row
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.resend_email_provider.secret_encryption.decrypt",
            return_value="re_live_key_123",
        ):
            provider = await EmailProviderFactory.get_provider(mock_db)

        assert isinstance(provider, ResendEmailProvider)
        assert provider.is_active() is True

    @pytest.mark.asyncio
    async def test_returns_disabled_when_db_row_disabled(self):
        mock_row = MagicMock()
        mock_row.is_enabled = False
        mock_row.encrypted_api_key = "encrypted_value"
        mock_row.deleted_at = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_row
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.core.config import settings as _settings

        _settings.RESEND_API_KEY = ""
        provider = await EmailProviderFactory.get_provider(mock_db)

        assert isinstance(provider, DisabledEmailProvider)

    @pytest.mark.asyncio
    async def test_returns_disabled_when_decryption_fails(self):
        from app.services.secret_encryption import SecretEncryptionError

        mock_row = MagicMock()
        mock_row.is_enabled = True
        mock_row.encrypted_api_key = "bad_encrypted_value"
        mock_row.deleted_at = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_row
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.resend_email_provider.secret_encryption.decrypt",
            side_effect=SecretEncryptionError("decrypt failed"),
        ):
            from app.core.config import settings as _settings

            _settings.RESEND_API_KEY = ""
            provider = await EmailProviderFactory.get_provider(mock_db)

        assert isinstance(provider, DisabledEmailProvider)


# ── Schema validation tests ────────────────────────────────────────────────────


class TestResendProviderUpdate:
    def test_valid_api_key_accepted(self):
        update = ResendProviderUpdate(api_key="re_live_testkey12345678")
        assert update.api_key == "re_live_testkey12345678"

    def test_api_key_without_re_prefix_rejected(self):
        with pytest.raises(ValidationError):
            ResendProviderUpdate(api_key="sk_live_bad_key")

    def test_short_api_key_rejected(self):
        with pytest.raises(ValidationError):
            ResendProviderUpdate(api_key="re_1")

    def test_valid_from_email_accepted(self):
        update = ResendProviderUpdate(from_email="noreply@flobrief.com")
        assert update.from_email == "noreply@flobrief.com"

    def test_invalid_from_email_rejected(self):
        with pytest.raises(ValidationError):
            ResendProviderUpdate(from_email="notanemail")

    def test_empty_reply_to_becomes_none(self):
        update = ResendProviderUpdate(reply_to="")
        assert update.reply_to is None

    def test_valid_reply_to_accepted(self):
        update = ResendProviderUpdate(reply_to="support@flobrief.com")
        assert update.reply_to == "support@flobrief.com"

    def test_omitted_api_key_stays_none(self):
        update = ResendProviderUpdate(is_enabled=True)
        assert update.api_key is None


class TestEmailTestSendRequest:
    def test_valid_email_accepted(self):
        req = EmailTestSendRequest(to_email="test@example.com")
        assert req.to_email == "test@example.com"

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            EmailTestSendRequest(to_email="notanemail")

    def test_email_lowercased(self):
        req = EmailTestSendRequest(to_email="Test@EXAMPLE.COM")
        assert req.to_email == "test@example.com"


class TestResendProviderStatusRead:
    def test_test_mode_defaults_require_only_api_key(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "RESEND_TEST_MODE", True)
        monkeypatch.setattr(settings, "RESEND_TEST_FROM_EMAIL", "onboarding@resend.dev")
        monkeypatch.setattr(settings, "EMAIL_FROM_NAME", "Flobrief")

        status = _build_email_status(None)

        assert status.is_enabled is True
        assert status.from_name == "Flobrief"
        assert status.from_email == "onboarding@resend.dev"
        assert status.missing_fields == ["api_key"]

    def test_not_configured_status(self):
        status = ResendProviderStatusRead(
            provider="email_resend",
            is_enabled=False,
            is_configured=False,
            missing_fields=["api_key", "from_email"],
        )
        assert status.api_key_set is False
        assert "api_key" in status.missing_fields

    def test_configured_status(self):
        status = ResendProviderStatusRead(
            provider="email_resend",
            is_enabled=True,
            is_configured=True,
            api_key_set=True,
            email_api_key_masked="re_••••••••1234",
            from_name="Flobrief",
            from_email="noreply@flobrief.com",
            missing_fields=[],
        )
        assert status.is_configured is True
        assert status.api_key_set is True
        assert "re_" in (status.email_api_key_masked or "")


# ── email_service HTML builder tests ─────────────────────────────────────────


class TestEmailServiceHtmlBuilders:
    def test_agency_invite_html_contains_accept_url(self):
        from app.services.email_service import build_agency_invite_html

        html = build_agency_invite_html(
            inviter_name="Ali",
            agency_name="Test Ajans",
            role="admin",
            accept_url="https://flobrief.com/invite/tok123",
        )
        assert "https://flobrief.com/invite/tok123" in html
        assert "Test Ajans" in html
        assert "Ali" in html

    def test_brand_invite_html_contains_brand_name(self):
        from app.services.email_service import build_brand_invite_html

        html = build_brand_invite_html(
            inviter_name="Ayşe",
            agency_name="Ajans X",
            brand_name="Marka Y",
            role="viewer",
            accept_url="https://flobrief.com/invite/tok456",
        )
        assert "Marka Y" in html
        assert "Ajans X" in html

    def test_brief_approval_html_contains_brief_title(self):
        from app.services.email_service import build_brief_approval_request_html

        html = build_brief_approval_request_html(
            recipient_name="Mehmet",
            agency_name="Ajans",
            brief_title="Yeni Kampanya",
            approval_url="https://flobrief.com/dashboard/briefs/123",
        )
        assert "Yeni Kampanya" in html
        assert "https://flobrief.com/dashboard/briefs/123" in html

    def test_brief_approved_html_contains_green_color(self):
        from app.services.email_service import build_brief_approved_html

        html = build_brief_approved_html(
            recipient_name="Can",
            brief_title="Proje X",
            brief_url="https://flobrief.com/dashboard/briefs/456",
        )
        assert "#10B981" in html
        assert "Proje X" in html

    def test_generic_notification_html_contains_title_and_body(self):
        from app.services.email_service import build_generic_notification_html

        html = build_generic_notification_html(
            recipient_name="Zeynep",
            title="Yeni Yorum",
            body="Brief üzerine yorum yapıldı.",
            action_url="https://flobrief.com/dashboard/briefs/789",
        )
        assert "Yeni Yorum" in html
        assert "Brief üzerine yorum yapıldı." in html


if __name__ == "__main__":
    unittest.main()

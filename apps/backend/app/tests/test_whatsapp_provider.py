"""Tests for WhatsApp provider architecture and Twilio settings API.

All tests use mocks/stubs — no real Twilio API calls are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import NotificationDeliveryStatus, WhatsAppProviderType
from app.services.secret_encryption import SecretEncryptionError, SecretEncryptionService
from app.services.whatsapp_provider import (
    DisabledWhatsAppProvider,
    TwilioWhatsAppProvider,
    WhatsAppProviderFactory,
)

# ── SecretEncryptionService ───────────────────────────────────────────────────


class TestSecretEncryptionService:
    def test_encrypt_decrypt_roundtrip(self) -> None:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        with patch("app.services.secret_encryption.settings") as mock_settings:
            mock_settings.FLOBRIEF_SECRET_ENCRYPTION_KEY = key
            svc = SecretEncryptionService()
            encrypted = svc.encrypt("my-secret-value")
            assert encrypted != "my-secret-value"
            assert svc.decrypt(encrypted) == "my-secret-value"

    def test_encrypt_raises_without_key(self) -> None:
        with patch("app.services.secret_encryption.settings") as mock_settings:
            mock_settings.FLOBRIEF_SECRET_ENCRYPTION_KEY = ""
            svc = SecretEncryptionService()
            with pytest.raises(SecretEncryptionError, match="FLOBRIEF_SECRET_ENCRYPTION_KEY"):
                svc.encrypt("secret")

    def test_decrypt_raises_without_key(self) -> None:
        with patch("app.services.secret_encryption.settings") as mock_settings:
            mock_settings.FLOBRIEF_SECRET_ENCRYPTION_KEY = ""
            svc = SecretEncryptionService()
            with pytest.raises(SecretEncryptionError):
                svc.decrypt("anything")

    def test_is_configured_false_when_no_key(self) -> None:
        with patch("app.services.secret_encryption.settings") as mock_settings:
            mock_settings.FLOBRIEF_SECRET_ENCRYPTION_KEY = ""
            assert SecretEncryptionService.is_configured() is False

    def test_is_configured_true_when_key_set(self) -> None:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        with patch("app.services.secret_encryption.settings") as mock_settings:
            mock_settings.FLOBRIEF_SECRET_ENCRYPTION_KEY = key
            assert SecretEncryptionService.is_configured() is True

    def test_encrypt_empty_raises(self) -> None:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        with patch("app.services.secret_encryption.settings") as mock_settings:
            mock_settings.FLOBRIEF_SECRET_ENCRYPTION_KEY = key
            svc = SecretEncryptionService()
            with pytest.raises(SecretEncryptionError):
                svc.encrypt("")

    def test_db_never_stores_plain_text(self) -> None:
        """Encrypted value must not equal plaintext — verifies encryption happened."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        with patch("app.services.secret_encryption.settings") as mock_settings:
            mock_settings.FLOBRIEF_SECRET_ENCRYPTION_KEY = key
            svc = SecretEncryptionService()
            plain = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            encrypted = svc.encrypt(plain)
            assert plain not in encrypted
            assert encrypted != plain


# ── DisabledWhatsAppProvider ─────────────────────────────────────────────────


class TestDisabledWhatsAppProvider:
    def test_send_returns_not_configured(self) -> None:
        provider = DisabledWhatsAppProvider()
        result = provider.send_message("+905001234567", "test")
        assert result.status == NotificationDeliveryStatus.NOT_CONFIGURED.value
        assert result.provider_message_id is None

    def test_skipped_returns_skipped(self) -> None:
        provider = DisabledWhatsAppProvider()
        result = provider.skipped()
        assert result.status == NotificationDeliveryStatus.SKIPPED.value

    def test_validate_config_is_false(self) -> None:
        assert DisabledWhatsAppProvider().validate_config() is False

    def test_provider_name(self) -> None:
        assert DisabledWhatsAppProvider().get_provider_name() == "disabled"


# ── TwilioWhatsAppProvider ────────────────────────────────────────────────────


class TestTwilioWhatsAppProvider:
    def _make_provider(self, sandbox: bool = True) -> TwilioWhatsAppProvider:
        return TwilioWhatsAppProvider(
            account_sid="ACtest1234567890",
            auth_token="auth_token_value",
            from_number="whatsapp:+14155238886",
            sandbox=sandbox,
        )

    def test_send_success(self) -> None:
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"sid": "SM123456"}

        with patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = provider.send_message("+905001234567", "Test message")

        assert result.status == NotificationDeliveryStatus.SENT.value
        assert result.provider_message_id == "SM123456"
        assert result.error_message is None

    def test_send_twilio_error(self) -> None:
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Invalid to number"}

        with patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = provider.send_message("+905001234567", "Test")

        assert result.status == NotificationDeliveryStatus.FAILED.value
        assert result.provider_message_id is None
        assert "400" in (result.error_message or "")

    def test_send_network_error(self) -> None:
        import httpx

        provider = self._make_provider()

        with patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.ConnectTimeout("timeout")
            mock_client_cls.return_value = mock_client

            result = provider.send_message("+905001234567", "Test")

        assert result.status == NotificationDeliveryStatus.FAILED.value
        assert "Network error" in (result.error_message or "")

    def test_provider_name_sandbox(self) -> None:
        assert self._make_provider(sandbox=True).get_provider_name() == "twilio_sandbox"

    def test_provider_name_production(self) -> None:
        assert self._make_provider(sandbox=False).get_provider_name() == "twilio_production"

    def test_validate_config_true(self) -> None:
        assert self._make_provider().validate_config() is True

    def test_to_phone_normalized_with_whatsapp_prefix(self) -> None:
        """Provider should add whatsapp: prefix when not present."""
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"sid": "SM999"}

        with patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            provider.send_message("+905001234567", "msg")

            call_args = mock_client.post.call_args
            assert call_args[1]["data"]["To"] == "whatsapp:+905001234567"


# ── WhatsAppProviderFactory ───────────────────────────────────────────────────


class TestWhatsAppProviderFactory:
    async def test_returns_disabled_when_feature_flag_off(self) -> None:
        with patch("app.services.whatsapp_provider.settings") as mock_settings:
            mock_settings.WHATSAPP_NOTIFICATIONS_ENABLED = False
            db = AsyncMock()
            provider = await WhatsAppProviderFactory.get_provider(db)
            assert isinstance(provider, DisabledWhatsAppProvider)

    async def test_returns_disabled_when_no_db_row(self) -> None:
        with patch("app.services.whatsapp_provider.settings") as mock_settings:
            mock_settings.WHATSAPP_NOTIFICATIONS_ENABLED = True

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)

            provider = await WhatsAppProviderFactory.get_provider(mock_db)
            assert isinstance(provider, DisabledWhatsAppProvider)

    async def test_returns_twilio_provider_when_configured(self) -> None:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        fernet = Fernet(key.encode())

        def enc(v: str) -> str:
            return fernet.encrypt(v.encode()).decode()

        mock_row = MagicMock()
        mock_row.is_enabled = True
        mock_row.provider_type = WhatsAppProviderType.TWILIO_SANDBOX.value
        mock_row.encrypted_account_sid = enc("ACtest123")
        mock_row.encrypted_auth_token = enc("auth_tok")
        mock_row.encrypted_whatsapp_from = enc("whatsapp:+14155238886")
        mock_row.encrypted_messaging_service_sid = None
        mock_row.deleted_at = None

        with (
            patch("app.services.whatsapp_provider.settings") as mock_settings,
            patch("app.services.whatsapp_provider.secret_encryption") as mock_enc,
        ):
            mock_settings.WHATSAPP_NOTIFICATIONS_ENABLED = True
            mock_enc.decrypt = lambda v: fernet.decrypt(v.encode()).decode()

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_row
            mock_db.execute = AsyncMock(return_value=mock_result)

            provider = await WhatsAppProviderFactory.get_provider(mock_db)
            assert isinstance(provider, TwilioWhatsAppProvider)

    async def test_returns_disabled_on_encryption_error(self) -> None:
        mock_row = MagicMock()
        mock_row.is_enabled = True
        mock_row.provider_type = WhatsAppProviderType.TWILIO_SANDBOX.value
        mock_row.encrypted_account_sid = "bad_encrypted_value"
        mock_row.encrypted_auth_token = "bad"
        mock_row.encrypted_whatsapp_from = "bad"
        mock_row.deleted_at = None

        with (
            patch("app.services.whatsapp_provider.settings") as mock_settings,
            patch("app.services.whatsapp_provider.secret_encryption") as mock_enc,
        ):
            mock_settings.WHATSAPP_NOTIFICATIONS_ENABLED = True
            mock_enc.decrypt.side_effect = SecretEncryptionError("bad key")

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_row
            mock_db.execute = AsyncMock(return_value=mock_result)

            provider = await WhatsAppProviderFactory.get_provider(mock_db)
            assert isinstance(provider, DisabledWhatsAppProvider)


# ── API endpoint contract tests (no DB) ──────────────────────────────────────


class TestTwilioProviderEndpointContracts:
    async def test_get_whatsapp_provider_requires_platform_admin(self, client: object) -> None:
        from httpx import AsyncClient

        assert isinstance(client, AsyncClient)
        resp = await client.get("/api/v1/platform/notification-providers/whatsapp")
        assert resp.status_code in (401, 403)

    async def test_patch_whatsapp_provider_requires_platform_admin(self, client: object) -> None:
        from httpx import AsyncClient

        assert isinstance(client, AsyncClient)
        resp = await client.patch(
            "/api/v1/platform/notification-providers/whatsapp",
            json={"is_enabled": True},
        )
        assert resp.status_code in (401, 403)

    async def test_test_send_requires_platform_admin(self, client: object) -> None:
        from httpx import AsyncClient

        assert isinstance(client, AsyncClient)
        resp = await client.post(
            "/api/v1/platform/notification-providers/whatsapp/test",
            json={"to_phone": "+905001234567"},
        )
        assert resp.status_code in (401, 403)


# ── Opt-in / skipped logic ────────────────────────────────────────────────────


class TestWhatsAppOptIn:
    def test_disabled_provider_skipped_for_missing_phone(self) -> None:
        """When user has no phone, delivery should be skipped."""
        provider = DisabledWhatsAppProvider()
        result = provider.skipped()
        assert result.status == NotificationDeliveryStatus.SKIPPED.value

    def test_provider_error_does_not_raise(self) -> None:
        """Provider errors must NOT propagate — they return FAILED status."""
        provider = TwilioWhatsAppProvider(
            account_sid="ACtest",
            auth_token="token",
            from_number="+14155238886",
        )
        with patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            import httpx as httpx_mod

            mock_client.post.side_effect = httpx_mod.RequestError("err")
            mock_client_cls.return_value = mock_client
            result = provider.send_message("+905001234567", "body")
        assert result.status == NotificationDeliveryStatus.FAILED.value


# ── send_template_message / test_connection / get_sender_status / error mapping ──


class TestTwilioTemplateSendAndConnection:
    def _make_provider(self) -> TwilioWhatsAppProvider:
        return TwilioWhatsAppProvider(
            account_sid="ACtest1234567890",
            auth_token="auth_token_value",
            from_number="whatsapp:+14155238886",
            sandbox=True,
        )

    def test_send_template_message_uses_content_sid_not_body(self) -> None:
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"sid": "SMtemplate1"}

        with patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = provider.send_template_message(
                "+905001234567", "HXcontenttemplate", {"1": "Flobrief"}
            )

            call_kwargs = mock_client.post.call_args[1]
            assert call_kwargs["data"]["ContentSid"] == "HXcontenttemplate"
            assert "Body" not in call_kwargs["data"]
            assert "1" in call_kwargs["data"]["ContentVariables"]

        assert result.status == NotificationDeliveryStatus.SENT.value
        assert result.provider_message_id == "SMtemplate1"

    def test_send_template_message_error_uses_normalized_message(self) -> None:
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Invalid to number +905001234567"}

        with patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = provider.send_template_message("+905001234567", "HXtpl", {})

        assert result.status == NotificationDeliveryStatus.FAILED.value
        assert result.error_message is not None
        assert "905001234567" not in result.error_message

    def test_test_connection_ok(self) -> None:
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            check = provider.test_connection()

        assert check.ok is True

    def test_test_connection_auth_failure(self) -> None:
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Authenticate"}

        with patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            check = provider.test_connection()

        assert check.ok is False

    def test_get_sender_status_no_from_configured(self) -> None:
        provider = TwilioWhatsAppProvider(
            account_sid="ACtest", auth_token="token", from_number=""
        )
        check = provider.get_sender_status()
        assert check.ok is False

    def test_normalize_provider_error_categorizes_auth(self) -> None:
        resp = MagicMock()
        resp.status_code = 403
        resp.json.return_value = {"message": "Forbidden"}
        category, msg = TwilioWhatsAppProvider.normalize_provider_error(resp)
        assert category == "auth"
        assert "403" in msg

    def test_normalize_provider_error_categorizes_rate_limited(self) -> None:
        resp = MagicMock()
        resp.status_code = 429
        resp.json.return_value = {"message": "Too many requests"}
        category, _msg = TwilioWhatsAppProvider.normalize_provider_error(resp)
        assert category == "rate_limited"

    def test_normalize_provider_error_categorizes_server_error(self) -> None:
        resp = MagicMock()
        resp.status_code = 503
        resp.json.return_value = {"message": "Service unavailable"}
        category, _msg = TwilioWhatsAppProvider.normalize_provider_error(resp)
        assert category == "server_error"


class TestDisabledProviderNewMethods:
    def test_send_template_message_returns_not_configured(self) -> None:
        provider = DisabledWhatsAppProvider()
        result = provider.send_template_message("+905001234567", "HXtpl", {})
        assert result.status == NotificationDeliveryStatus.NOT_CONFIGURED.value

    def test_test_connection_not_ok(self) -> None:
        provider = DisabledWhatsAppProvider()
        assert provider.test_connection().ok is False

    def test_get_sender_status_not_ok(self) -> None:
        provider = DisabledWhatsAppProvider()
        assert provider.get_sender_status().ok is False


# ── Sandbox freeform test-send (Part 6A) ─────────────────────────────────────


class TestSandboxFreeformSend:
    def _sandbox_provider(self) -> TwilioWhatsAppProvider:
        return TwilioWhatsAppProvider(
            account_sid="ACtest1234567890",
            auth_token="auth_token_value",
            from_number="whatsapp:+14155238886",
            sandbox=True,
        )

    def _production_provider(self) -> TwilioWhatsAppProvider:
        return TwilioWhatsAppProvider(
            account_sid="ACtest1234567890",
            auth_token="auth_token_value",
            from_number="whatsapp:+905001112233",
            sandbox=False,
        )

    def test_is_official_sandbox_sender_true_for_real_sandbox_number(self) -> None:
        assert self._sandbox_provider().is_official_sandbox_sender() is True

    def test_is_official_sandbox_sender_false_for_production_sender(self) -> None:
        assert self._production_provider().is_official_sandbox_sender() is False

    def test_is_official_sandbox_sender_false_when_sandbox_flag_but_different_number(self) -> None:
        """provider_type=='twilio_sandbox' alone must not be enough — the exact
        Twilio-owned sandbox number is required (DECISION-081)."""
        provider = TwilioWhatsAppProvider(
            account_sid="ACtest",
            auth_token="token",
            from_number="whatsapp:+905009998877",
            sandbox=True,
        )
        assert provider.is_official_sandbox_sender() is False

    def test_send_sandbox_freeform_uses_fixed_body_not_content_sid(self) -> None:
        from app.services.whatsapp_provider import SANDBOX_FREEFORM_TEST_BODY

        provider = self._sandbox_provider()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"sid": "SMsandbox1"}

        with patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = provider.send_sandbox_freeform_test_message("+905001234567")

            call_kwargs = mock_client.post.call_args[1]
            assert call_kwargs["data"]["Body"] == SANDBOX_FREEFORM_TEST_BODY
            assert "ContentSid" not in call_kwargs["data"]
            assert call_kwargs["data"]["From"] == "whatsapp:+14155238886"
            assert call_kwargs["data"]["To"] == "whatsapp:+905001234567"

        assert result.status == NotificationDeliveryStatus.SENT.value
        assert result.provider_message_id == "SMsandbox1"

    def test_send_sandbox_freeform_never_echoes_a_custom_body_argument(self) -> None:
        """The method takes no body/text parameter at all — there is no
        argument through which caller-supplied text could reach Twilio."""
        import inspect

        sig = inspect.signature(TwilioWhatsAppProvider.send_sandbox_freeform_test_message)
        assert list(sig.parameters) == ["self", "to_phone"]

    def test_send_sandbox_freeform_rejects_non_sandbox_sender(self) -> None:
        """Defense in depth: even if called directly against a production-configured
        provider, the method itself refuses rather than trusting the caller."""
        provider = self._production_provider()
        result = provider.send_sandbox_freeform_test_message("+905001234567")
        assert result.status == NotificationDeliveryStatus.NOT_CONFIGURED.value

    def test_send_sandbox_freeform_includes_status_callback_when_backend_url_configured(
        self,
    ) -> None:
        provider = self._sandbox_provider()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"sid": "SMsandbox2"}

        with (
            patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls,
            patch("app.services.whatsapp_provider.settings") as mock_settings,
        ):
            mock_settings.BACKEND_PUBLIC_URL = "https://api.example.com"
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            provider.send_sandbox_freeform_test_message("+905001234567")

            call_kwargs = mock_client.post.call_args[1]
            assert (
                call_kwargs["data"]["StatusCallback"]
                == "https://api.example.com/api/v1/webhooks/twilio/whatsapp"
            )

    def test_send_sandbox_freeform_omits_status_callback_when_backend_url_unset(self) -> None:
        provider = self._sandbox_provider()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"sid": "SMsandbox3"}

        with (
            patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls,
            patch("app.services.whatsapp_provider.settings") as mock_settings,
        ):
            mock_settings.BACKEND_PUBLIC_URL = ""
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            provider.send_sandbox_freeform_test_message("+905001234567")

            call_kwargs = mock_client.post.call_args[1]
            assert "StatusCallback" not in call_kwargs["data"]

    def test_send_sandbox_freeform_error_uses_normalized_message(self) -> None:
        provider = self._sandbox_provider()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Invalid to number +905001234567"}

        with patch("app.services.whatsapp_provider.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = provider.send_sandbox_freeform_test_message("+905001234567")

        assert result.status == NotificationDeliveryStatus.FAILED.value
        assert result.error_message is not None
        assert "905001234567" not in result.error_message


class TestSeedScriptProviderKeyRegression:
    """Regression guard for the audited bug: the seed script previously wrote
    provider="twilio_whatsapp" while every real consumer (this module, the
    webhook verifier, the admin API) filters on "whatsapp_twilio" — making
    seeded rows silently invisible. This asserts the script now uses the same
    key string the runtime actually queries."""

    def test_seed_script_uses_the_same_provider_key_as_the_factory(self) -> None:
        import pathlib

        script_path = (
            pathlib.Path(__file__).resolve().parents[2] / "scripts" / "seed_provider_settings.py"
        )
        source = script_path.read_text(encoding="utf-8")
        assert 'provider="whatsapp_twilio"' in source
        assert '"twilio_whatsapp"' not in source

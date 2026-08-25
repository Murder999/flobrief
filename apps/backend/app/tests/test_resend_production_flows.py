from __future__ import annotations

import logging
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.models.enums import NotificationDeliveryStatus, NotificationEventType
from app.schemas.auth import PasswordResetRequest, ResendVerificationRequest
from app.services import email_service
from app.services.auth_service import AuthService
from app.services.invitation_service import InvitationService
from app.services.notification_dispatcher import NotificationDispatcher
from app.services.resend_email_provider import EmailDeliveryResult


def _sent_result() -> EmailDeliveryResult:
    return EmailDeliveryResult(
        status=NotificationDeliveryStatus.SENT.value,
        provider="resend",
        provider_message_id="email_test_123",
        error_message=None,
    )


def _provider() -> MagicMock:
    provider = MagicMock()
    provider.get_provider_name.return_value = "resend"
    provider.is_active.return_value = True
    provider.send = AsyncMock(return_value=_sent_result())
    return provider


@pytest.mark.asyncio
async def test_verification_email_uses_resend_and_production_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "FRONTEND_PUBLIC_URL", "https://postpiloter.com")
    provider = _provider()
    with patch(
        "app.services.email_service.EmailProviderFactory.get_provider",
        new=AsyncMock(return_value=provider),
    ):
        result = await email_service.send_verification_email(
            AsyncMock(), "member@example.com", "Member", "verify token/1"
        )

    assert result.status == NotificationDeliveryStatus.SENT.value
    html = provider.send.await_args.kwargs["html"]
    assert "https://postpiloter.com/auth/verify-email?token=verify%20token%2F1" in html
    assert "localhost" not in html
    assert "flobrief.com" not in html


@pytest.mark.asyncio
async def test_password_reset_email_uses_resend_and_production_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "FRONTEND_PUBLIC_URL", "https://postpiloter.com")
    provider = _provider()
    with patch(
        "app.services.email_service.EmailProviderFactory.get_provider",
        new=AsyncMock(return_value=provider),
    ):
        await email_service.send_password_reset_email(
            AsyncMock(), "member@example.com", "Member", "reset-token"
        )

    html = provider.send.await_args.kwargs["html"]
    assert "https://postpiloter.com/auth/reset-password?token=reset-token" in html


@pytest.mark.asyncio
async def test_agency_and_brand_invites_use_canonical_accept_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "FRONTEND_PUBLIC_URL", "https://postpiloter.com")
    db = AsyncMock()
    service = InvitationService(db)
    deliver = AsyncMock(return_value=_sent_result())

    with patch("app.services.email_service.deliver_transactional_email", new=deliver):
        await service._send_agency_invite_email(
            to_email="agency@example.com",
            agency_name="Agency",
            inviter_name="Owner",
            role="admin",
            token="agency-token",
            message=None,
        )
        await service._send_brand_invite_email(
            to_email="brand@example.com",
            agency_name="Agency",
            brand_name="Brand",
            inviter_name="Owner",
            role="brand_member",
            token="brand-token",
            message=None,
        )

    assert deliver.await_count == 2
    first_html = deliver.await_args_list[0].kwargs["html_body"]
    second_html = deliver.await_args_list[1].kwargs["html_body"]
    assert "https://postpiloter.com/auth/accept-invite?token=agency-token" in first_html
    assert "https://postpiloter.com/auth/accept-invite?token=brand-token" in second_html


@pytest.mark.asyncio
async def test_resend_invitation_rotates_token_and_sends_new_link() -> None:
    db = AsyncMock()
    service = InvitationService(db)
    invitation = MagicMock(
        id=uuid.uuid4(),
        agency_id=uuid.uuid4(),
        brand_id=None,
        invitation_type="agency",
        email="invitee@example.com",
        role="admin",
        resent_count=1,
        is_pending=True,
    )
    actor = MagicMock(id=uuid.uuid4(), full_name="Owner")
    service.invite_repo.get_by_id = AsyncMock(return_value=invitation)
    service.invite_repo.update = AsyncMock()
    service._can_manage_invitation = AsyncMock(return_value=True)
    service.agency_repo.get_by_id = AsyncMock(return_value=MagicMock(name="Agency"))
    service._send_agency_invite_email = AsyncMock()
    activity_repo = MagicMock()
    activity_repo.create = AsyncMock()

    with (
        patch("app.services.invitation_service.generate_token", return_value="rotated-token"),
        patch("app.repositories.activity.ActivityLogRepository", return_value=activity_repo),
    ):
        _, token = await service.resend_by_id(invitation.id, actor)

    assert token == "rotated-token"
    service.invite_repo.update.assert_awaited_once()
    db.commit.assert_awaited_once()
    service._send_agency_invite_email.assert_awaited_once()
    assert service._send_agency_invite_email.await_args.kwargs["token"] == "rotated-token"


@pytest.mark.asyncio
async def test_resend_invitation_rejects_expired_or_used_invitation() -> None:
    service = InvitationService(AsyncMock())
    invitation = MagicMock(id=uuid.uuid4(), is_pending=False)
    actor = MagicMock(id=uuid.uuid4())
    service.invite_repo.get_by_id = AsyncMock(return_value=invitation)
    service._can_manage_invitation = AsyncMock(return_value=True)
    service._send_agency_invite_email = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await service.resend_by_id(invitation.id, actor)

    assert exc_info.value.status_code == 400
    service._send_agency_invite_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_verification_resend_rotates_token_then_calls_email_service() -> None:
    db = AsyncMock()
    service = AuthService(db)
    user = MagicMock(
        id=uuid.uuid4(),
        email="member@example.com",
        full_name="Member",
        locale="tr",
        is_deleted=False,
        is_verified=False,
    )
    service.user_repo.get_by_email = AsyncMock(return_value=user)
    service.token_repo.revoke_all_for_user = AsyncMock()
    service.token_repo.create = AsyncMock()
    send = AsyncMock(return_value=_sent_result())

    with (
        patch("app.services.auth_service.generate_token", return_value="new-verify-token"),
        patch("app.services.auth_service.email_service.send_verification_email", new=send),
    ):
        await service.resend_verification(ResendVerificationRequest(email="member@example.com"))

    service.token_repo.revoke_all_for_user.assert_awaited_once()
    service.token_repo.create.assert_awaited_once()
    db.commit.assert_awaited_once()
    send.assert_awaited_once_with(
        db, "member@example.com", "Member", "new-verify-token", "tr"
    )


@pytest.mark.asyncio
async def test_forgot_password_rotates_token_then_calls_email_service() -> None:
    db = AsyncMock()
    service = AuthService(db)
    user = MagicMock(
        id=uuid.uuid4(),
        email="member@example.com",
        full_name="Member",
        locale="en",
        is_deleted=False,
        is_active=True,
    )
    service.user_repo.get_by_email = AsyncMock(return_value=user)
    service.token_repo.revoke_all_for_user = AsyncMock()
    service.token_repo.create = AsyncMock()
    send = AsyncMock(return_value=_sent_result())

    with (
        patch("app.services.auth_service.generate_token", return_value="new-reset-token"),
        patch("app.services.auth_service.email_service.send_password_reset_email", new=send),
    ):
        await service.forgot_password(PasswordResetRequest(email="member@example.com"))

    service.token_repo.revoke_all_for_user.assert_awaited_once()
    service.token_repo.create.assert_awaited_once()
    db.commit.assert_awaited_once()
    send.assert_awaited_once_with(
        db, "member@example.com", "Member", "new-reset-token", "en"
    )


@pytest.mark.asyncio
async def test_notification_email_uses_resend_provider_and_public_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "FRONTEND_PUBLIC_URL", "https://postpiloter.com")
    dispatcher = NotificationDispatcher.__new__(NotificationDispatcher)
    event = MagicMock(
        event_type=NotificationEventType.BRIEF_SUBMITTED.value,
        payload={
            "brief_id": str(uuid.uuid4()),
            "brief_title": "Launch",
            "agency_name": "Agency",
        },
    )
    user = MagicMock(email="member@example.com", full_name="Member")
    provider = _provider()

    result = await dispatcher._deliver_event_email(event, user, "Brief submitted", "Body", provider)

    assert result.status == NotificationDeliveryStatus.SENT.value
    html = provider.send.await_args.kwargs["html"]
    assert "https://postpiloter.com/dashboard/briefs/" in html


@pytest.mark.asyncio
async def test_safe_email_log_never_contains_provider_exception_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)
    secret = "re_secret_that_must_not_be_logged"
    with patch(
        "app.services.email_service.EmailProviderFactory.get_provider",
        new=AsyncMock(side_effect=RuntimeError(secret)),
    ):
        result = await email_service.deliver_transactional_email(
            AsyncMock(),
            to_email="member@example.com",
            subject="Subject",
            html_body="<p>Body</p>",
            message_type="security_test",
        )

    assert result.status == NotificationDeliveryStatus.FAILED.value
    assert secret not in caplog.text
    assert "message_type=security_test" in caplog.text


def test_production_realtime_proxy_and_frontend_are_wired_for_postpiloter() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    compose = (repo_root / "docker-compose.prod.yml").read_text(encoding="utf-8")
    nginx = (repo_root / "infra/nginx/nginx.conf").read_text(encoding="utf-8")
    hook = (repo_root / "apps/frontend/components/notifications/useNotificationFeed.ts").read_text(
        encoding="utf-8"
    )

    assert "NEXT_PUBLIC_WS_URL:-wss://postpiloter.com" in compose
    assert "server_name postpiloter.com www.postpiloter.com;" in nginx
    assert "location = /api/v1/notifications/realtime" in nginx
    assert "proxy_set_header Upgrade $http_upgrade;" in nginx
    assert 'proxy_set_header Connection "upgrade";' in nginx
    assert 'message.type === "notifications.changed"' in hook
    assert "scheduleReconnect" in hook
    assert "refresh" in hook


def test_production_settings_reject_local_or_legacy_public_origins() -> None:
    base = {
        "_env_file": None,
        "SECRET_KEY": "test-secret-key-that-is-long-enough-for-validation",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@postgres:5432/app",
        "APP_ENV": "production",
        "APP_DEBUG": False,
        "FRONTEND_URL": "https://postpiloter.com",
        "FRONTEND_PUBLIC_URL": "https://postpiloter.com",
        "BACKEND_PUBLIC_URL": "https://postpiloter.com",
        "CORS_ORIGINS": "https://postpiloter.com",
        "EMAIL_FROM": "noreply@postpiloter.com",
        "EMAIL_FROM_NAME": "PostPiloter",
        "RESEND_TEST_MODE": False,
    }
    production = Settings(**base)
    assert production.FRONTEND_PUBLIC_URL == "https://postpiloter.com"

    with pytest.raises(ValidationError, match="FRONTEND_PUBLIC_URL"):
        Settings(**{**base, "FRONTEND_PUBLIC_URL": "http://localhost:3000"})

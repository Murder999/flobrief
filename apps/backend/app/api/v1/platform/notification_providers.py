"""Platform admin endpoints for WhatsApp/Twilio and Resend email provider configuration.

Access: platform_admin only.
Security: secrets encrypted in DB, never returned in responses.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_platform_admin_user
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.models.enums import WhatsAppProviderType
from app.models.platform_provider_settings import PlatformProviderSetting
from app.models.user import User
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.repositories.platform_provider_settings import PlatformProviderSettingRepository
from app.schemas.email_provider import (
    ClearEmailSecretRequest,
    EmailTestSendRequest,
    EmailTestSendResult,
    ResendProviderStatusRead,
    ResendProviderUpdate,
)
from app.schemas.whatsapp_provider import (
    ClearSecretRequest,
    ConnectionVerifyResult,
    TwilioProviderStatusRead,
    TwilioProviderUpdate,
    WhatsAppTestSendRequest,
    WhatsAppTestSendResult,
)
from app.services.secret_encryption import SecretEncryptionError, secret_encryption
from app.services.whatsapp_connection_status import compute_connection_status

_PROVIDER_KEY = "whatsapp_twilio"
_EMAIL_PROVIDER_KEY = "email_resend"

platform_notification_providers_router = APIRouter(
    prefix="/notification-providers", tags=["platform-notification-providers"]
)


def _mask_account_sid(sid: str) -> str:
    """AC + stars + last 4: AC************1234"""
    if len(sid) <= 6:
        return "AC" + "*" * 4
    return "AC" + "*" * (len(sid) - 6) + sid[-4:]


def _mask_phone(phone: str) -> str:
    clean = phone.replace("whatsapp:", "")
    if len(clean) <= 6:
        return "***"
    return clean[:4] + "***" + clean[-2:]


def _build_status(row: PlatformProviderSetting | None) -> TwilioProviderStatusRead:
    if row is None:
        return TwilioProviderStatusRead(
            provider=_PROVIDER_KEY,
            provider_type=WhatsAppProviderType.DISABLED.value,
            is_enabled=False,
            is_configured=False,
            connection_status=compute_connection_status(None),
            missing_fields=["account_sid", "auth_token", "whatsapp_from"],
        )

    missing: list[str] = []
    if not row.encrypted_account_sid:
        missing.append("account_sid")
    if not row.encrypted_auth_token:
        missing.append("auth_token")
    if not row.encrypted_whatsapp_from:
        missing.append("whatsapp_from")

    return TwilioProviderStatusRead(
        provider=row.provider,
        provider_type=row.provider_type,
        is_enabled=row.is_enabled,
        is_configured=len(missing) == 0,
        connection_status=compute_connection_status(row),
        account_sid_masked=(
            _mask_account_sid(row.account_sid_last4 or "") if row.encrypted_account_sid else None
        ),
        whatsapp_from_masked=row.whatsapp_from_masked,
        auth_token_set=bool(row.encrypted_auth_token),
        webhook_verify_token_set=bool(row.encrypted_webhook_verify_token),
        messaging_service_sid_set=bool(row.encrypted_messaging_service_sid),
        configured_at=row.configured_at,
        configured_by_user_id=row.configured_by_user_id,
        last_connection_check_at=row.last_connection_check_at,
        last_connection_error=row.last_connection_error,
        missing_fields=missing,
    )


@platform_notification_providers_router.get("/whatsapp", response_model=TwilioProviderStatusRead)
async def get_whatsapp_provider(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> TwilioProviderStatusRead:
    repo = PlatformProviderSettingRepository(db)
    row = await repo.get_by_provider(_PROVIDER_KEY)
    return _build_status(row)


@platform_notification_providers_router.patch("/whatsapp", response_model=TwilioProviderStatusRead)
async def update_whatsapp_provider(
    data: TwilioProviderUpdate,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> TwilioProviderStatusRead:
    if not secret_encryption.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "FLOBRIEF_SECRET_ENCRYPTION_KEY ayarlanmamış. "
                "Secret kaydedilemiyor. Lütfen backend ortam değişkenini ayarlayın."
            ),
        )

    repo = PlatformProviderSettingRepository(db)
    audit_repo = PlatformAuditLogRepository(db)

    row = await repo.get_by_provider(_PROVIDER_KEY)
    if row is None:
        row = PlatformProviderSetting(provider=_PROVIDER_KEY)
        db.add(row)
        await db.flush()

    changed_fields: list[str] = []

    if data.provider_type is not None:
        row.provider_type = data.provider_type.value
        changed_fields.append("provider_type")

    if data.is_enabled is not None:
        row.is_enabled = data.is_enabled
        changed_fields.append("is_enabled")

    if data.account_sid is not None:
        row.encrypted_account_sid = secret_encryption.encrypt(data.account_sid)
        row.account_sid_last4 = data.account_sid[-4:]
        changed_fields.append("account_sid")

    if data.auth_token is not None:
        row.encrypted_auth_token = secret_encryption.encrypt(data.auth_token)
        changed_fields.append("auth_token")

    if data.whatsapp_from is not None:
        phone = data.whatsapp_from
        if not phone.startswith("whatsapp:"):
            phone = f"whatsapp:{phone}"
        row.encrypted_whatsapp_from = secret_encryption.encrypt(phone)
        row.whatsapp_from_masked = _mask_phone(phone)
        changed_fields.append("whatsapp_from")

    if data.messaging_service_sid is not None:
        row.encrypted_messaging_service_sid = secret_encryption.encrypt(data.messaging_service_sid)
        changed_fields.append("messaging_service_sid")

    if data.webhook_verify_token is not None:
        row.encrypted_webhook_verify_token = secret_encryption.encrypt(data.webhook_verify_token)
        changed_fields.append("webhook_verify_token")

    if changed_fields:
        row.configured_at = datetime.now(UTC)
        row.configured_by_user_id = admin.id

    db.add(row)
    await db.flush()
    await db.refresh(row)

    # Audit log — no secret values, only field names
    await audit_repo.create(
        admin_user_id=admin.id,
        action="platform.whatsapp_provider.updated",
        target_type="platform_provider_setting",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"fields_changed": changed_fields},
    )
    await db.commit()

    return _build_status(row)


@platform_notification_providers_router.post(
    "/whatsapp/test", response_model=WhatsAppTestSendResult
)
async def test_whatsapp_send(
    data: WhatsAppTestSendRequest,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> WhatsAppTestSendResult:
    from app.core.rate_limiter import rate_limit_whatsapp_test_send
    from app.services.whatsapp_provider import WhatsAppProviderFactory

    await rate_limit_whatsapp_test_send(str(admin.id))

    provider = await WhatsAppProviderFactory.get_provider(db)

    message = data.message or "Flobrief WhatsApp test mesajı. Platform yapılandırması başarılı."
    result = provider.send_message(data.to_phone, message)

    to_masked = _mask_phone(data.to_phone)
    return WhatsAppTestSendResult(
        status=result.status,
        provider=result.provider,
        provider_message_id=result.provider_message_id,
        error_message=result.error_message,
        to_phone_masked=to_masked,
    )


@platform_notification_providers_router.post(
    "/whatsapp/verify-connection", response_model=ConnectionVerifyResult
)
async def verify_whatsapp_connection(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionVerifyResult:
    """Real, single, short credential check against Twilio — never fabricated.

    Persists the result on the provider row so GET /whatsapp reflects a
    genuinely-verified `connected`/`degraded`/`error` status afterward instead
    of the config-completeness-only `sandbox` default.
    """
    from app.services.whatsapp_provider import DisabledWhatsAppProvider, WhatsAppProviderFactory

    repo = PlatformProviderSettingRepository(db)
    row = await repo.get_by_provider(_PROVIDER_KEY)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider ayarı bulunamadı")

    provider = await WhatsAppProviderFactory.get_provider(db)
    now = datetime.now(UTC)

    if isinstance(provider, DisabledWhatsAppProvider):
        row.last_connection_status = "error"
        row.last_connection_error = "Provider yapılandırılmamış veya devre dışı"
    else:
        connection = provider.test_connection()
        if not connection.ok:
            row.last_connection_status = "error"
            row.last_connection_error = connection.detail
        else:
            sender = provider.get_sender_status()
            row.last_connection_status = "ok" if sender.ok else "degraded"
            row.last_connection_error = None if sender.ok else sender.detail

    row.last_connection_check_at = now
    db.add(row)
    await db.commit()
    await db.refresh(row)

    return ConnectionVerifyResult(
        connection_status=row.last_connection_status or "error",
        detail=row.last_connection_error,
        checked_at=now,
    )


@platform_notification_providers_router.post(
    "/whatsapp/clear-secret", response_model=TwilioProviderStatusRead
)
async def clear_whatsapp_secret(
    data: ClearSecretRequest,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> TwilioProviderStatusRead:
    repo = PlatformProviderSettingRepository(db)
    audit_repo = PlatformAuditLogRepository(db)

    row = await repo.get_by_provider(_PROVIDER_KEY)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider ayarı bulunamadı")

    field_map = {
        "auth_token": "encrypted_auth_token",
        "account_sid": ("encrypted_account_sid", "account_sid_last4"),
        "whatsapp_from": ("encrypted_whatsapp_from", "whatsapp_from_masked"),
        "messaging_service_sid": "encrypted_messaging_service_sid",
        "webhook_verify_token": "encrypted_webhook_verify_token",
    }

    target = field_map[data.field]
    if isinstance(target, tuple):
        for attr in target:
            setattr(row, attr, None)
    else:
        setattr(row, target, None)

    db.add(row)
    await db.flush()
    await db.refresh(row)

    await audit_repo.create(
        admin_user_id=admin.id,
        action="platform.whatsapp_provider.secret_cleared",
        target_type="platform_provider_setting",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"field_cleared": data.field},
    )
    await db.commit()

    return _build_status(row)


# ── Email / Resend provider ────────────────────────────────────────────────────


def _mask_api_key(key: str) -> str:
    """Fixed short mask: re_••••••••<last4> — always ≤20 chars, fits varchar(30)."""
    if len(key) <= 4:
        return "re_••••"
    return "re_••••••••" + key[-4:]


def _build_email_status(row: PlatformProviderSetting | None) -> ResendProviderStatusRead:
    default_from_email = (
        settings.RESEND_TEST_FROM_EMAIL if settings.RESEND_TEST_MODE else settings.EMAIL_FROM
    )
    db_key_valid = False
    if row is not None and row.is_enabled and row.encrypted_api_key:
        try:
            db_key_valid = bool(secret_encryption.decrypt(row.encrypted_api_key))
        except SecretEncryptionError:
            db_key_valid = False

    env_is_configured = bool(settings.RESEND_API_KEY and default_from_email)
    if settings.is_production and env_is_configured:
        return ResendProviderStatusRead(
            provider=_EMAIL_PROVIDER_KEY,
            configuration_source="environment",
            is_enabled=True,
            is_configured=True,
            api_key_set=True,
            email_api_key_masked=_mask_api_key(settings.RESEND_API_KEY),
            from_name=settings.EMAIL_FROM_NAME,
            from_email=default_from_email,
            reply_to=settings.EMAIL_REPLY_TO or None,
            configured_at=row.configured_at if row is not None else None,
            configured_by_user_id=(row.configured_by_user_id if row is not None else None),
            missing_fields=[],
        )

    if db_key_valid and row is not None:
        return ResendProviderStatusRead(
            provider=row.provider,
            configuration_source="database",
            is_enabled=True,
            is_configured=True,
            api_key_set=True,
            email_api_key_masked=row.email_api_key_masked,
            from_name=row.email_from_name or settings.EMAIL_FROM_NAME,
            from_email=row.email_from_email or default_from_email,
            reply_to=row.email_reply_to or settings.EMAIL_REPLY_TO or None,
            configured_at=row.configured_at,
            configured_by_user_id=row.configured_by_user_id,
            missing_fields=[],
        )

    if env_is_configured:
        return ResendProviderStatusRead(
            provider=_EMAIL_PROVIDER_KEY,
            configuration_source="environment",
            is_enabled=True,
            is_configured=True,
            api_key_set=True,
            email_api_key_masked=_mask_api_key(settings.RESEND_API_KEY),
            from_name=settings.EMAIL_FROM_NAME,
            from_email=default_from_email,
            reply_to=settings.EMAIL_REPLY_TO or None,
            configured_at=row.configured_at if row is not None else None,
            configured_by_user_id=(row.configured_by_user_id if row is not None else None),
            missing_fields=[],
        )

    stored_key = bool(row and row.encrypted_api_key)
    missing = [] if stored_key else ["api_key"]
    if row is not None and row.is_enabled and stored_key and not db_key_valid:
        missing = ["api_key"]

    return ResendProviderStatusRead(
        provider=row.provider if row is not None else _EMAIL_PROVIDER_KEY,
        configuration_source="none",
        is_enabled=False,
        is_configured=stored_key and not (row and row.is_enabled and not db_key_valid),
        api_key_set=stored_key,
        email_api_key_masked=row.email_api_key_masked if row is not None else None,
        from_name=(row.email_from_name if row is not None else None) or settings.EMAIL_FROM_NAME,
        from_email=(row.email_from_email if row is not None else None) or default_from_email,
        reply_to=(row.email_reply_to if row is not None else None)
        or settings.EMAIL_REPLY_TO
        or None,
        configured_at=row.configured_at if row is not None else None,
        configured_by_user_id=(row.configured_by_user_id if row is not None else None),
        missing_fields=missing,
    )


@platform_notification_providers_router.get("/email", response_model=ResendProviderStatusRead)
async def get_email_provider(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ResendProviderStatusRead:
    repo = PlatformProviderSettingRepository(db)
    row = await repo.get_by_provider(_EMAIL_PROVIDER_KEY)
    return _build_email_status(row)


@platform_notification_providers_router.patch("/email", response_model=ResendProviderStatusRead)
async def update_email_provider(
    data: ResendProviderUpdate,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ResendProviderStatusRead:
    if not secret_encryption.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=("FLOBRIEF_SECRET_ENCRYPTION_KEY ayarlanmamış. " "Secret kaydedilemiyor."),
        )

    repo = PlatformProviderSettingRepository(db)
    audit_repo = PlatformAuditLogRepository(db)

    row = await repo.get_by_provider(_EMAIL_PROVIDER_KEY)
    if row is None:
        row = PlatformProviderSetting(
            provider=_EMAIL_PROVIDER_KEY,
            is_enabled=settings.RESEND_TEST_MODE,
            email_from_name=settings.EMAIL_FROM_NAME,
            email_from_email=(
                settings.RESEND_TEST_FROM_EMAIL
                if settings.RESEND_TEST_MODE
                else settings.EMAIL_FROM
            ),
            email_reply_to=settings.EMAIL_REPLY_TO or None,
        )
        db.add(row)
        await db.flush()

    changed_fields: list[str] = []

    if data.is_enabled is not None:
        row.is_enabled = data.is_enabled
        changed_fields.append("is_enabled")

    if data.api_key is not None:
        row.encrypted_api_key = secret_encryption.encrypt(data.api_key)
        row.email_api_key_masked = _mask_api_key(data.api_key)
        changed_fields.append("api_key")

    if data.from_name is not None:
        row.email_from_name = data.from_name
        changed_fields.append("from_name")

    if data.from_email is not None:
        row.email_from_email = data.from_email
        changed_fields.append("from_email")

    if data.reply_to is not None:
        row.email_reply_to = data.reply_to or None
        changed_fields.append("reply_to")

    if changed_fields:
        row.configured_at = datetime.now(UTC)
        row.configured_by_user_id = admin.id

    db.add(row)
    await db.flush()
    await db.refresh(row)

    await audit_repo.create(
        admin_user_id=admin.id,
        action="platform.email_provider.updated",
        target_type="platform_provider_setting",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"fields_changed": changed_fields},
    )
    await db.commit()

    return _build_email_status(row)


@platform_notification_providers_router.post("/email/test", response_model=EmailTestSendResult)
async def test_email_send(
    data: EmailTestSendRequest,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> EmailTestSendResult:
    from app.services.resend_email_provider import EmailProviderFactory

    provider = await EmailProviderFactory.get_provider(db)

    subject = data.subject or f"{settings.EMAIL_FROM_NAME} — Test E-postası"
    message = (
        data.message
        or f"Bu bir {settings.EMAIL_FROM_NAME} platform test e-postasıdır. "
        "Yapılandırma başarılı."
    )
    html = f"""<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#0A0A0F;color:#F0F0F8;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px">
    <h1 style="color:#6366F1;font-size:24px;margin-bottom:8px">{settings.EMAIL_FROM_NAME}</h1>
    <h2 style="font-size:18px;margin-bottom:16px">Test E-postası</h2>
    <p style="color:#8888A8;margin-bottom:24px">{message}</p>
    <p style="color:#8888A8;font-size:12px;margin-top:24px;">Bu e-posta platform admin tarafından gönderilmiştir.</p>
  </div>
</body>
</html>"""

    result = await provider.send(to_email=data.to_email, subject=subject, html=html)

    email_local = data.to_email.split("@")[0]
    email_domain = data.to_email.split("@")[1] if "@" in data.to_email else ""
    masked = f"{email_local[:2]}{'•' * (len(email_local) - 2)}@{email_domain}"

    return EmailTestSendResult(
        status=result.status,
        provider=result.provider,
        provider_message_id=result.provider_message_id,
        error_message=result.error_message,
        to_email_masked=masked,
    )


@platform_notification_providers_router.post(
    "/email/clear-secret", response_model=ResendProviderStatusRead
)
async def clear_email_secret(
    data: ClearEmailSecretRequest,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ResendProviderStatusRead:
    repo = PlatformProviderSettingRepository(db)
    audit_repo = PlatformAuditLogRepository(db)

    row = await repo.get_by_provider(_EMAIL_PROVIDER_KEY)
    if row is None:
        raise HTTPException(status_code=404, detail="Email provider ayarı bulunamadı")

    if data.field == "api_key":
        row.encrypted_api_key = None
        row.email_api_key_masked = None
    else:
        raise HTTPException(status_code=400, detail=f"Geçersiz field: {data.field}")

    db.add(row)
    await db.flush()
    await db.refresh(row)

    await audit_repo.create(
        admin_user_id=admin.id,
        action="platform.email_provider.secret_cleared",
        target_type="platform_provider_setting",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"field_cleared": data.field},
    )
    await db.commit()

    return _build_email_status(row)

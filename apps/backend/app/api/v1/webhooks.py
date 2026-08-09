"""Twilio webhook endpoint for WhatsApp delivery status updates.

Security:
- Full X-Twilio-Signature HMAC-SHA1 verification per Twilio's request-validation
  spec (https://www.twilio.com/docs/usage/security#validating-requests), keyed on
  the account's Auth Token.
- Duplicate events handled idempotently via provider_message_id lookup.
- Invalid/unknown events are rejected with 400.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.request_validator import RequestValidator

from app.core.config import settings
from app.db.session import get_db
from app.models.enums import NotificationDeliveryStatus
from app.models.notification import NotificationDelivery
from app.models.user import User
from app.repositories.activity import ActivityLogRepository
from app.repositories.notification import NotificationDeliveryRepository
from app.schemas.whatsapp_provider import WebhookEventRead
from app.services.phone_utils import normalize_e164
from app.services.whatsapp_delivery_state_machine import apply_transition
from app.services.whatsapp_preference_service import set_whatsapp_consent

webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_TWILIO_DELIVERY_STATUS_MAP: dict[str, str] = {
    "queued": NotificationDeliveryStatus.QUEUED.value,
    "accepted": NotificationDeliveryStatus.ACCEPTED.value,
    "sent": NotificationDeliveryStatus.SENT.value,
    "delivered": NotificationDeliveryStatus.DELIVERED.value,
    "read": NotificationDeliveryStatus.READ.value,
    "failed": NotificationDeliveryStatus.FAILED.value,
    "undelivered": NotificationDeliveryStatus.FAILED.value,
}

# Twilio's ErrorMessage occasionally echoes the destination number back
# (e.g. "The number +905xxxxxxxx is not a valid WhatsApp participant") — this
# strips any 7-15 digit run before the message is ever persisted or returned,
# same masking rule as TwilioWhatsAppProvider.normalize_provider_error.
_DIGIT_RUN_RE = re.compile(r"\+?\d{7,15}")
_MAX_SAFE_ERROR_LEN = 200


def _sanitize_callback_error(error_code: str | None, error_message: str | None) -> str | None:
    if not error_code and not error_message:
        return None
    safe_message = _DIGIT_RUN_RE.sub("***", error_message or "")[:_MAX_SAFE_ERROR_LEN]
    if error_code:
        return f"Twilio callback error {error_code}: {safe_message}".strip()
    return safe_message or None


def _webhook_url(request: Request) -> str:
    """The exact URL Twilio signed against — must match the console-configured
    webhook URL byte-for-byte, including query string."""
    if settings.BACKEND_PUBLIC_URL:
        base = settings.BACKEND_PUBLIC_URL.rstrip("/")
        suffix = str(request.url).split(str(request.base_url).rstrip("/") + "/", 1)[-1]
        return f"{base}/{suffix}"
    return str(request.url)


async def _verify_twilio_signature(request: Request, db: AsyncSession) -> None:
    """Verify the Twilio webhook signature against the account Auth Token.

    Fails closed: an enabled Twilio provider with no configured Auth Token, a
    missing signature header, or a signature mismatch all result in a 403 —
    never a silent pass-through.
    """
    from app.models.platform_provider_settings import PlatformProviderSetting
    from app.services.secret_encryption import SecretEncryptionError, secret_encryption

    stmt = select(PlatformProviderSetting).where(
        PlatformProviderSetting.provider == "whatsapp_twilio",
        PlatformProviderSetting.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None or not row.is_enabled:
        # Provider not configured at all — nothing to verify against, and the
        # lookup below will find no matching delivery record either way.
        return

    if not row.encrypted_auth_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Twilio provider is enabled but has no Auth Token configured",
        )

    try:
        auth_token = secret_encryption.decrypt(row.encrypted_auth_token)
    except SecretEncryptionError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unable to verify webhook signature",
        ) from err

    x_twilio_sig = request.headers.get("X-Twilio-Signature")
    if not x_twilio_sig:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing Twilio webhook signature",
        )

    form = await request.form()
    params = {k: str(v) for k, v in form.multi_items()}
    validator = RequestValidator(auth_token)
    if not validator.validate(_webhook_url(request), params, x_twilio_sig):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio webhook signature",
        )


@webhook_router.post("/twilio/whatsapp", response_model=WebhookEventRead)
async def twilio_whatsapp_webhook(
    request: Request,
    MessageSid: Annotated[str | None, Form()] = None,  # noqa: N803
    MessageStatus: Annotated[str | None, Form()] = None,  # noqa: N803
    SmsSid: Annotated[str | None, Form()] = None,  # noqa: N803
    SmsStatus: Annotated[str | None, Form()] = None,  # noqa: N803
    ErrorCode: Annotated[str | None, Form()] = None,  # noqa: N803
    ErrorMessage: Annotated[str | None, Form()] = None,  # noqa: N803
    db: AsyncSession = Depends(get_db),
) -> WebhookEventRead:
    """Twilio does not scope this callback to a tenant — the only trustworthy
    identifier in the payload is MessageSid, so tenant isolation here means
    exactly one thing: only ever look a delivery up by provider_message_id,
    never accept or trust an agency_id/user_id from the request, and never
    let one SID's callback touch any row but its own exact match."""
    await _verify_twilio_signature(request, db)

    sid = MessageSid or SmsSid
    raw_status = MessageStatus or SmsStatus

    if not sid or not raw_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing MessageSid or MessageStatus",
        )

    mapped_status = _TWILIO_DELIVERY_STATUS_MAP.get(raw_status.lower())

    # Find delivery record by provider_message_id (idempotent) — the only
    # identifier in this payload we trust; never accept a caller-supplied id.
    result = await db.execute(
        select(NotificationDelivery).where(
            NotificationDelivery.provider_message_id == sid,
            NotificationDelivery.deleted_at.is_(None),
        )
    )
    delivery = result.scalar_one_or_none()

    if delivery is None:
        # Unknown SID — still return 200 to prevent Twilio from retrying.
        # Never touches any row, so an unknown/forged SID can't affect
        # another tenant's delivery.
        return WebhookEventRead(
            processed=False,
            provider_message_id=sid,
            delivery_status=mapped_status,
            applied=False,
        )

    if mapped_status is None:
        # Recognized SID, but a raw status string we don't map — acknowledge
        # without mutating anything (fail-closed on unknown input).
        return WebhookEventRead(
            processed=True,
            provider_message_id=sid,
            delivery_status=None,
            applied=False,
        )

    is_failure = mapped_status == NotificationDeliveryStatus.FAILED.value
    safe_error = _sanitize_callback_error(ErrorCode, ErrorMessage) if is_failure else None

    transition = apply_transition(
        delivery,
        mapped_status,
        now=datetime.now(UTC),
        error_message=safe_error,
        failure_category="provider_reported_failure" if is_failure else None,
        provider_message_id=None,  # already matched on this value; never rewritten here
    )
    if transition.applied:
        db.add(delivery)
        await db.commit()

    return WebhookEventRead(
        processed=True,
        provider_message_id=sid,
        delivery_status=mapped_status,
        applied=transition.applied,
    )


# ── Inbound WhatsApp STOP/opt-out (Part 6B-3) ───────────────────────────────
#
# Twilio's inbound-message webhook (a normal user reply to any WhatsApp
# conversation the account is part of) — distinct from the status-callback
# endpoint above, which never carries a `Body`/`From` pair for a message the
# recipient sent to us. Same signature verification, same fail-closed
# posture, same "never trust anything but what we look up ourselves" rule.

_STOP_KEYWORDS: frozenset[str] = frozenset({"STOP", "DUR", "IPTAL", "CANCEL", "UNSUBSCRIBE"})
# Maps every Turkish "i" variant (dotted/dotless, upper/lower) to plain ASCII
# "I" before the final .upper() — so "iptal"/"İPTAL"/"İptal"/"IPTAL" all
# normalize to the same "IPTAL" keyword regardless of locale casing rules.
_TR_I_VARIANTS = str.maketrans({"i": "I", "İ": "I", "ı": "I", "I": "I"})
_TRAILING_PUNCTUATION_RE = re.compile(r"[.,!?;:¡¿\s]+$")


def _normalize_inbound_keyword(body: str) -> str:
    stripped = body.strip()
    stripped = _TRAILING_PUNCTUATION_RE.sub("", stripped)
    return stripped.translate(_TR_I_VARIANTS).upper()


async def _find_unique_user_by_whatsapp_phone(
    db: AsyncSession, from_field: str
) -> User | list[User]:
    """Resolve the inbound `whatsapp:+E164` sender to exactly one user.

    Returns the matched User, or a (possibly empty) list when the match is
    not unique — an empty list means "unknown number", a list with 2+ users
    means "ambiguous, do not act". Phone numbers are not guaranteed to be
    stored pre-normalized, so an exact-string WHERE clause would silently
    miss legitimate matches; this does a cheap SQL prefilter on the last 4
    raw digits (bounds the candidate set) and verifies precisely with
    normalize_e164 in Python. Known limit: still O(candidates) in Python,
    acceptable for inbound STOP volume but not a hot path pattern.
    """
    raw_phone = from_field.removeprefix("whatsapp:")
    incoming = normalize_e164(raw_phone)
    if incoming is None:
        return []

    digit_suffix = re.sub(r"\D", "", incoming)[-4:]
    if not digit_suffix:
        return []

    result = await db.execute(
        select(User).where(
            User.phone_number.is_not(None),
            User.phone_number.like(f"%{digit_suffix}"),
            User.deleted_at.is_(None),
        )
    )
    candidates = [
        u for u in result.scalars().all() if normalize_e164(u.phone_number or "") == incoming
    ]
    if len(candidates) == 1:
        return candidates[0]
    return candidates


@webhook_router.post("/twilio/whatsapp/inbound")
async def twilio_whatsapp_inbound_webhook(
    request: Request,
    From: Annotated[str | None, Form()] = None,  # noqa: N803
    Body: Annotated[str | None, Form()] = None,  # noqa: N803
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _verify_twilio_signature(request, db)

    empty_twiml = Response(content="<Response></Response>", media_type="text/xml")

    if not From or Body is None:
        return empty_twiml

    keyword = _normalize_inbound_keyword(Body)
    if keyword not in _STOP_KEYWORDS:
        # Not an opt-out keyword — this endpoint never auto-replies or
        # re-opts a user in; unrecognized inbound text is a silent no-op.
        return empty_twiml

    match = await _find_unique_user_by_whatsapp_phone(db, From)
    activity_repo = ActivityLogRepository(db)

    if isinstance(match, list):
        if len(match) > 1:
            # Ambiguous — never guess which account to opt out. Audited so
            # the collision is visible without ever storing the raw phone.
            await activity_repo.create(
                action="whatsapp_stop_ambiguous_phone",
                entity_type="user",
                entity_id=None,
                meta={"keyword": keyword, "candidate_count": len(match)},
            )
            await db.commit()
        # Zero matches (unknown number) — no audit, no mutation, no reply.
        return empty_twiml

    user = match
    now = datetime.now(UTC)
    await set_whatsapp_consent(db, user=user, opt_in=False)

    delivery_repo = NotificationDeliveryRepository(db)
    cancelled_count = await delivery_repo.cancel_pending_retries_for_user(
        user.id, reason="WhatsApp STOP opt-out", now=now
    )

    await activity_repo.create(
        action="whatsapp_stop_opt_out",
        entity_type="user",
        entity_id=user.id,
        meta={"keyword": keyword, "cancelled_pending_retries": cancelled_count},
    )
    await db.commit()

    return empty_twiml

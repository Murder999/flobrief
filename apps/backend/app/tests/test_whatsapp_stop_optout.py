"""Backend tests for the inbound WhatsApp STOP/opt-out webhook (Part 6B-3).

POST /api/v1/webhooks/twilio/whatsapp/inbound — signature-verified, keyword
normalization (STOP/DUR/IPTAL/İPTAL/CANCEL/UNSUBSCRIBE), safe phone
matching, ambiguous/unknown-number handling, pending-retry cancellation,
and email/in-app preferences left untouched.
"""

# ruff: noqa: F811 -- `twilio_provider_row` is an imported fixture reused as
# a test-method parameter name (standard pytest cross-module fixture reuse).
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from twilio.request_validator import RequestValidator

from app.db.session import AsyncSessionLocal
from app.models.activity import ActivityLog
from app.models.enums import NotificationChannel, NotificationDeliveryStatus
from app.models.notification import NotificationDelivery, NotificationEvent, NotificationPreference
from app.models.user import User
from app.tests.test_twilio_webhook import (  # noqa: F401
    AUTH_TOKEN,
    _decrypt_patch,
    twilio_provider_row,
)

INBOUND_PATH = "/api/v1/webhooks/twilio/whatsapp/inbound"
INBOUND_URL = "http://test" + INBOUND_PATH


def _sign_inbound(params: dict[str, str]) -> str:
    validator = RequestValidator(AUTH_TOKEN)
    return validator.compute_signature(INBOUND_URL, params)


async def _post_inbound(client: AsyncClient, params: dict[str, str]):
    sig = _sign_inbound(params)
    with _decrypt_patch():
        return await client.post(
            INBOUND_PATH, data=params, headers={"X-Twilio-Signature": sig}
        )


async def _make_optin_user(phone_number: str) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"stopuser-{uuid.uuid4().hex[:8]}@test.local",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name="Stop Test User",
            user_type="agency_user",
            is_active=True,
            is_verified=True,
            phone_number=phone_number,
            whatsapp_opt_in=True,
            whatsapp_opt_in_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()
        session.add(
            NotificationPreference(id=uuid.uuid4(), user_id=user.id, whatsapp_enabled=True)
        )
        await session.commit()
        return user.id


async def _cleanup_user(user_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        deliveries = (
            await session.execute(
                select(NotificationDelivery).where(
                    NotificationDelivery.recipient_user_id == user_id
                )
            )
        ).scalars().all()
        for d in deliveries:
            await session.delete(d)

        pref = (
            await session.execute(
                select(NotificationPreference).where(NotificationPreference.user_id == user_id)
            )
        ).scalar_one_or_none()
        if pref is not None:
            await session.delete(pref)

        logs = (
            await session.execute(select(ActivityLog).where(ActivityLog.entity_id == user_id))
        ).scalars().all()
        for log in logs:
            await session.delete(log)

        user = await session.get(User, user_id)
        if user is not None:
            await session.delete(user)
        await session.commit()


async def _get_user(user_id: uuid.UUID) -> User:
    async with AsyncSessionLocal() as session:
        return await session.get(User, user_id)


async def _get_pref(user_id: uuid.UUID) -> NotificationPreference:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        return result.scalar_one()


class TestStopKeywordNormalization:
    async def test_stop_uppercase_opts_out(self, client: AsyncClient, twilio_provider_row) -> None:
        phone = "+90555" + str(uuid.uuid4().int)[:7]
        user_id = await _make_optin_user(phone)
        try:
            resp = await _post_inbound(
                client, {"From": f"whatsapp:{phone}", "Body": "STOP", "MessageSid": "SMstop1"}
            )
            assert resp.status_code == 200
            user = await _get_user(user_id)
            assert user.whatsapp_opt_in is False
            assert user.whatsapp_opt_out_at is not None
            pref = await _get_pref(user_id)
            assert pref.whatsapp_enabled is False
        finally:
            await _cleanup_user(user_id)

    async def test_lowercase_dur_opts_out(self, client: AsyncClient, twilio_provider_row) -> None:
        phone = "+90555" + str(uuid.uuid4().int)[:7]
        user_id = await _make_optin_user(phone)
        try:
            resp = await _post_inbound(
                client, {"From": f"whatsapp:{phone}", "Body": " dur ", "MessageSid": "SMdur1"}
            )
            assert resp.status_code == 200
            user = await _get_user(user_id)
            assert user.whatsapp_opt_in is False
        finally:
            await _cleanup_user(user_id)

    async def test_turkish_dotted_i_iptal_opts_out(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        phone = "+90555" + str(uuid.uuid4().int)[:7]
        user_id = await _make_optin_user(phone)
        try:
            resp = await _post_inbound(
                client, {"From": f"whatsapp:{phone}", "Body": "İPTAL", "MessageSid": "SMiptal1"}
            )
            assert resp.status_code == 200
            user = await _get_user(user_id)
            assert user.whatsapp_opt_in is False
        finally:
            await _cleanup_user(user_id)

    async def test_lowercase_iptal_with_punctuation_opts_out(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        phone = "+90555" + str(uuid.uuid4().int)[:7]
        user_id = await _make_optin_user(phone)
        try:
            resp = await _post_inbound(
                client, {"From": f"whatsapp:{phone}", "Body": "iptal!", "MessageSid": "SMiptal2"}
            )
            assert resp.status_code == 200
            user = await _get_user(user_id)
            assert user.whatsapp_opt_in is False
        finally:
            await _cleanup_user(user_id)

    async def test_unrecognized_message_is_a_noop(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        phone = "+90555" + str(uuid.uuid4().int)[:7]
        user_id = await _make_optin_user(phone)
        try:
            resp = await _post_inbound(
                client,
                {"From": f"whatsapp:{phone}", "Body": "merhaba, brief ne zaman hazir olur?"},
            )
            assert resp.status_code == 200
            user = await _get_user(user_id)
            assert user.whatsapp_opt_in is True  # untouched
        finally:
            await _cleanup_user(user_id)


class TestStopPhoneMatching:
    async def test_unknown_phone_does_not_opt_out_anyone(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        never_registered = "+90555" + str(uuid.uuid4().int)[:7]
        resp = await _post_inbound(
            client, {"From": f"whatsapp:{never_registered}", "Body": "STOP"}
        )
        assert resp.status_code == 200  # no error, just a safe no-op

    async def test_ambiguous_phone_opts_out_nobody_and_audits(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        shared_phone = "+90555" + str(uuid.uuid4().int)[:7]
        user_a = await _make_optin_user(shared_phone)
        user_b = await _make_optin_user(shared_phone)
        try:
            resp = await _post_inbound(
                client, {"From": f"whatsapp:{shared_phone}", "Body": "STOP"}
            )
            assert resp.status_code == 200
            ua = await _get_user(user_a)
            ub = await _get_user(user_b)
            assert ua.whatsapp_opt_in is True
            assert ub.whatsapp_opt_in is True

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ActivityLog).where(
                        ActivityLog.action == "whatsapp_stop_ambiguous_phone"
                    )
                )
                rows = result.scalars().all()
                assert any(r.meta.get("candidate_count") == 2 for r in rows)
        finally:
            await _cleanup_user(user_a)
            await _cleanup_user(user_b)


class TestStopSideEffects:
    async def test_pending_whatsapp_retries_are_cancelled(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        phone = "+90555" + str(uuid.uuid4().int)[:7]
        user_id = await _make_optin_user(phone)
        try:
            async with AsyncSessionLocal() as session:
                event = NotificationEvent(id=uuid.uuid4(), event_type="brief.created", payload={})
                session.add(event)
                await session.flush()
                delivery = NotificationDelivery(
                    id=uuid.uuid4(),
                    event_id=event.id,
                    channel=NotificationChannel.WHATSAPP.value,
                    status=NotificationDeliveryStatus.FAILED.value,
                    provider="twilio_production",
                    recipient_user_id=user_id,
                    next_retry_at=datetime.now(UTC) + timedelta(minutes=5),
                    idempotency_key=f"test-stop-{uuid.uuid4().hex}",
                )
                session.add(delivery)
                await session.commit()
                delivery_id = delivery.id

            resp = await _post_inbound(client, {"From": f"whatsapp:{phone}", "Body": "STOP"})
            assert resp.status_code == 200

            async with AsyncSessionLocal() as session:
                d = await session.get(NotificationDelivery, delivery_id)
                assert d.status == NotificationDeliveryStatus.CANCELLED.value
                assert d.next_retry_at is None
                assert d.cancelled_at is not None
                await session.delete(d)
                await session.commit()
        finally:
            await _cleanup_user(user_id)

    async def test_stop_does_not_touch_email_or_in_app_preferences(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        phone = "+90555" + str(uuid.uuid4().int)[:7]
        user_id = await _make_optin_user(phone)
        try:
            async with AsyncSessionLocal() as session:
                pref = (
                    await session.execute(
                        select(NotificationPreference).where(
                            NotificationPreference.user_id == user_id
                        )
                    )
                ).scalar_one()
                pref.email_enabled = True
                pref.in_app_enabled = True
                session.add(pref)
                await session.commit()

            await _post_inbound(client, {"From": f"whatsapp:{phone}", "Body": "STOP"})

            pref_after = await _get_pref(user_id)
            assert pref_after.email_enabled is True
            assert pref_after.in_app_enabled is True
            assert pref_after.whatsapp_enabled is False
        finally:
            await _cleanup_user(user_id)

    async def test_successful_stop_creates_audit_log_without_raw_phone(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        phone = "+90555" + str(uuid.uuid4().int)[:7]
        user_id = await _make_optin_user(phone)
        try:
            await _post_inbound(client, {"From": f"whatsapp:{phone}", "Body": "STOP"})

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ActivityLog).where(
                        ActivityLog.action == "whatsapp_stop_opt_out",
                        ActivityLog.entity_id == user_id,
                    )
                )
                log = result.scalar_one()
                assert phone not in str(log.meta)
                assert log.meta["keyword"] == "STOP"
        finally:
            await _cleanup_user(user_id)

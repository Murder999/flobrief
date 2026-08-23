"""Integration tests for the Twilio WhatsApp status webhook signature
verification (app/api/v1/webhooks.py), now backed by the official
twilio.request_validator.RequestValidator instead of a hand-rolled HMAC.

Uses the real Postgres test DB (via the `client` fixture) for the enabled
provider row; the auth-token decrypt step is mocked (identical pattern to
test_whatsapp_provider.py) so no real Fernet key is required in the test env.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from twilio.request_validator import RequestValidator

from app.db.session import AsyncSessionLocal
from app.models.enums import NotificationChannel, NotificationDeliveryStatus, WhatsAppProviderType
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.platform_provider_settings import PlatformProviderSetting

AUTH_TOKEN = "test-twilio-auth-token-0123456789"
WEBHOOK_PATH = "/api/v1/webhooks/twilio/whatsapp"
WEBHOOK_URL = "http://test" + WEBHOOK_PATH


@pytest.fixture
async def twilio_provider_row():
    async with AsyncSessionLocal() as session:
        row = PlatformProviderSetting(
            id=uuid.uuid4(),
            provider="whatsapp_twilio",
            provider_type=WhatsAppProviderType.TWILIO_SANDBOX.value,
            is_enabled=True,
            encrypted_account_sid="enc-sid",
            encrypted_auth_token="enc-token",
        )
        session.add(row)
        await session.commit()
        try:
            yield row
        finally:
            await session.delete(await session.get(PlatformProviderSetting, row.id))
            await session.commit()


def _sign(params: dict[str, str]) -> str:
    validator = RequestValidator(AUTH_TOKEN)
    return validator.compute_signature(WEBHOOK_URL, params)


def _decrypt_patch():
    return patch(
        "app.services.secret_encryption.secret_encryption.decrypt",
        return_value=AUTH_TOKEN,
    )


class TestTwilioWebhookSignature:
    async def test_missing_signature_header_rejected(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        with _decrypt_patch():
            resp = await client.post(
                WEBHOOK_PATH,
                data={"MessageSid": "SMunknown", "MessageStatus": "delivered"},
            )
        assert resp.status_code == 403

    async def test_invalid_signature_rejected(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        params = {"MessageSid": "SMunknown", "MessageStatus": "delivered"}
        with _decrypt_patch():
            resp = await client.post(
                WEBHOOK_PATH,
                data=params,
                headers={"X-Twilio-Signature": "not-a-real-signature"},
            )
        assert resp.status_code == 403

    async def test_valid_signature_accepted_unknown_sid_returns_200(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        params = {"MessageSid": "SMunknown-" + uuid.uuid4().hex, "MessageStatus": "delivered"}
        sig = _sign(params)
        with _decrypt_patch():
            resp = await client.post(
                WEBHOOK_PATH,
                data=params,
                headers={"X-Twilio-Signature": sig},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed"] is False

    async def test_tampered_param_after_signing_rejected(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        params = {"MessageSid": "SMoriginal", "MessageStatus": "delivered"}
        sig = _sign(params)
        tampered = {"MessageSid": "SMoriginal", "MessageStatus": "failed"}
        with _decrypt_patch():
            resp = await client.post(
                WEBHOOK_PATH,
                data=tampered,
                headers={"X-Twilio-Signature": sig},
            )
        assert resp.status_code == 403

    async def test_duplicate_named_params_do_not_bypass_verification(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        """A signature computed over one value for a repeated field name must
        not validate against a request carrying a different value for it."""
        params = {"MessageSid": "SMdup", "MessageStatus": "delivered"}
        sig = _sign(params)
        # httpx allows sending the same field name twice via a list of tuples.
        with _decrypt_patch():
            resp = await client.post(
                WEBHOOK_PATH,
                content=("MessageSid=SMdup&MessageSid=SMother&MessageStatus=delivered"),
                headers={
                    "X-Twilio-Signature": sig,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
        assert resp.status_code == 403

    async def test_missing_auth_token_configured_rejects(self, client: AsyncClient) -> None:
        async with AsyncSessionLocal() as session:
            row = PlatformProviderSetting(
                id=uuid.uuid4(),
                provider="whatsapp_twilio",
                provider_type=WhatsAppProviderType.TWILIO_SANDBOX.value,
                is_enabled=True,
                encrypted_account_sid="enc-sid",
                encrypted_auth_token=None,
            )
            session.add(row)
            await session.commit()
            row_id = row.id
        try:
            resp = await client.post(
                WEBHOOK_PATH,
                data={"MessageSid": "SMx", "MessageStatus": "delivered"},
                headers={"X-Twilio-Signature": "any"},
            )
            assert resp.status_code == 403
        finally:
            async with AsyncSessionLocal() as session:
                obj = await session.get(PlatformProviderSetting, row_id)
                if obj is not None:
                    await session.delete(obj)
                    await session.commit()


class TestTwilioWebhookStatusParsing:
    """Part 6A: queued/sent/delivered/read/failed must map to distinct statuses,
    and delivered_at/read_at must be set on the matched delivery row."""

    async def _make_delivery(self, sid: str) -> uuid.UUID:
        async with AsyncSessionLocal() as session:
            event = NotificationEvent(
                id=uuid.uuid4(),
                event_type="system.test_notification",
                payload={},
            )
            session.add(event)
            await session.flush()
            delivery = NotificationDelivery(
                id=uuid.uuid4(),
                event_id=event.id,
                channel=NotificationChannel.WHATSAPP.value,
                status=NotificationDeliveryStatus.SENT.value,
                provider="twilio_sandbox",
                provider_message_id=sid,
            )
            session.add(delivery)
            await session.commit()
            return delivery.id

    async def _get_delivery(self, delivery_id: uuid.UUID) -> NotificationDelivery:
        async with AsyncSessionLocal() as session:
            return await session.get(NotificationDelivery, delivery_id)

    async def test_delivered_status_sets_delivered_at(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        sid = "SMdelivered-" + uuid.uuid4().hex
        delivery_id = await self._make_delivery(sid)
        params = {"MessageSid": sid, "MessageStatus": "delivered"}
        sig = _sign(params)
        with _decrypt_patch():
            resp = await client.post(WEBHOOK_PATH, data=params, headers={"X-Twilio-Signature": sig})
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed"] is True
        assert body["delivery_status"] == NotificationDeliveryStatus.DELIVERED.value

        delivery = await self._get_delivery(delivery_id)
        assert delivery.status == NotificationDeliveryStatus.DELIVERED.value
        assert delivery.delivered_at is not None
        assert delivery.read_at is None

    async def test_read_status_sets_read_at(self, client: AsyncClient, twilio_provider_row) -> None:
        sid = "SMread-" + uuid.uuid4().hex
        delivery_id = await self._make_delivery(sid)
        params = {"MessageSid": sid, "MessageStatus": "read"}
        sig = _sign(params)
        with _decrypt_patch():
            resp = await client.post(WEBHOOK_PATH, data=params, headers={"X-Twilio-Signature": sig})
        assert resp.status_code == 200
        assert resp.json()["delivery_status"] == NotificationDeliveryStatus.READ.value

        delivery = await self._get_delivery(delivery_id)
        assert delivery.status == NotificationDeliveryStatus.READ.value
        assert delivery.read_at is not None

    async def test_queued_status_parsed_distinctly(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        sid = "SMqueued-" + uuid.uuid4().hex
        await self._make_delivery(sid)
        params = {"MessageSid": sid, "MessageStatus": "queued"}
        sig = _sign(params)
        with _decrypt_patch():
            resp = await client.post(WEBHOOK_PATH, data=params, headers={"X-Twilio-Signature": sig})
        assert resp.status_code == 200
        assert resp.json()["delivery_status"] == NotificationDeliveryStatus.QUEUED.value


class TestTwilioWebhookStateMachine:
    """Part 6B-3: duplicate/out-of-order callback handling, error sanitization."""

    async def _make_delivery(self, sid: str, *, status: str) -> uuid.UUID:
        async with AsyncSessionLocal() as session:
            event = NotificationEvent(
                id=uuid.uuid4(), event_type="system.test_notification", payload={}
            )
            session.add(event)
            await session.flush()
            delivery = NotificationDelivery(
                id=uuid.uuid4(),
                event_id=event.id,
                channel=NotificationChannel.WHATSAPP.value,
                status=status,
                provider="twilio_sandbox",
                provider_message_id=sid,
            )
            session.add(delivery)
            await session.commit()
            return delivery.id

    async def _get_delivery(self, delivery_id: uuid.UUID) -> NotificationDelivery:
        async with AsyncSessionLocal() as session:
            return await session.get(NotificationDelivery, delivery_id)

    async def _post(self, client: AsyncClient, params: dict[str, str]) -> object:
        sig = _sign(params)
        with _decrypt_patch():
            return await client.post(WEBHOOK_PATH, data=params, headers={"X-Twilio-Signature": sig})

    async def test_duplicate_delivered_callback_second_call_not_applied(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        sid = "SMdupdel-" + uuid.uuid4().hex
        delivery_id = await self._make_delivery(sid, status=NotificationDeliveryStatus.SENT.value)
        params = {"MessageSid": sid, "MessageStatus": "delivered"}

        first = await self._post(client, params)
        assert first.json()["applied"] is True
        delivered_at_first = (await self._get_delivery(delivery_id)).delivered_at

        second = await self._post(client, params)
        assert second.status_code == 200
        assert second.json()["applied"] is False

        delivery = await self._get_delivery(delivery_id)
        assert delivery.status == NotificationDeliveryStatus.DELIVERED.value
        assert delivery.delivered_at == delivered_at_first

    async def test_out_of_order_queued_after_delivered_does_not_regress(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        sid = "SMooo-" + uuid.uuid4().hex
        delivery_id = await self._make_delivery(
            sid, status=NotificationDeliveryStatus.DELIVERED.value
        )
        resp = await self._post(client, {"MessageSid": sid, "MessageStatus": "queued"})
        assert resp.status_code == 200
        assert resp.json()["applied"] is False

        delivery = await self._get_delivery(delivery_id)
        assert delivery.status == NotificationDeliveryStatus.DELIVERED.value

    async def test_failed_after_read_does_not_regress(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        sid = "SMreadfail-" + uuid.uuid4().hex
        delivery_id = await self._make_delivery(sid, status=NotificationDeliveryStatus.READ.value)
        resp = await self._post(client, {"MessageSid": sid, "MessageStatus": "failed"})
        assert resp.status_code == 200
        assert resp.json()["applied"] is False

        delivery = await self._get_delivery(delivery_id)
        assert delivery.status == NotificationDeliveryStatus.READ.value

    async def test_failed_callback_records_sanitized_error_code_and_message(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        sid = "SMerr-" + uuid.uuid4().hex
        delivery_id = await self._make_delivery(sid, status=NotificationDeliveryStatus.SENT.value)
        params = {
            "MessageSid": sid,
            "MessageStatus": "failed",
            "ErrorCode": "63016",
            "ErrorMessage": "The number +905551234567 is not a valid WhatsApp participant",
        }
        resp = await self._post(client, params)
        assert resp.status_code == 200
        assert resp.json()["applied"] is True

        delivery = await self._get_delivery(delivery_id)
        assert delivery.status == NotificationDeliveryStatus.FAILED.value
        assert delivery.failure_category == "provider_reported_failure"
        assert "63016" in delivery.error_message
        assert "+905551234567" not in delivery.error_message
        assert "***" in delivery.error_message

    async def test_unrecognized_raw_status_acknowledged_without_mutation(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        sid = "SMunk-" + uuid.uuid4().hex
        delivery_id = await self._make_delivery(sid, status=NotificationDeliveryStatus.SENT.value)
        resp = await self._post(client, {"MessageSid": sid, "MessageStatus": "some-future-status"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed"] is True
        assert body["applied"] is False

        delivery = await self._get_delivery(delivery_id)
        assert delivery.status == NotificationDeliveryStatus.SENT.value

    async def test_unknown_sid_never_touches_another_deliverys_row(
        self, client: AsyncClient, twilio_provider_row
    ) -> None:
        real_sid = "SMreal-" + uuid.uuid4().hex
        delivery_id = await self._make_delivery(
            real_sid, status=NotificationDeliveryStatus.SENT.value
        )
        forged_sid = "SMforged-" + uuid.uuid4().hex
        resp = await self._post(client, {"MessageSid": forged_sid, "MessageStatus": "delivered"})
        assert resp.status_code == 200
        assert resp.json()["applied"] is False

        delivery = await self._get_delivery(delivery_id)
        assert delivery.status == NotificationDeliveryStatus.SENT.value

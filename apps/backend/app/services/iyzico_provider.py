"""iyzico payment provider.

Authentication: HMAC-SHA256 per iyzico API spec.
Card details NEVER touch Flobrief servers — CheckoutForm redirects to iyzico-hosted page.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from typing import Any

import httpx

from app.core.config import settings


class IyzicoError(Exception):
    def __init__(self, status_code: str, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


class IyzicoProvider:
    """iyzico REST API client. Uses async httpx for all requests."""

    def __init__(self) -> None:
        self.api_key = settings.IYZICO_API_KEY
        self.secret_key = settings.IYZICO_SECRET_KEY
        self.base_url = settings.IYZICO_BASE_URL.rstrip("/")

    def _auth_headers(self, body_str: str) -> dict[str, str]:
        random_str = secrets.token_hex(16)
        hash_input = self.secret_key + random_str + body_str
        digest = hashlib.sha256(hash_input.encode("utf-8")).digest()
        hash_b64 = base64.b64encode(digest).decode("utf-8")
        return {
            "Authorization": f"IYZWS {self.api_key}:{hash_b64}",
            "x-iyzi-rnd": random_str,
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        headers = self._auth_headers(body_str)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}{path}",
                content=body_str,
                headers=headers,
            )
        data: dict[str, Any] = resp.json()
        if data.get("status") != "success":
            raise IyzicoError(
                status_code=data.get("status", "failure"),
                error_code=data.get("errorCode", "UNKNOWN"),
                message=data.get("errorMessage", "iyzico request failed"),
            )
        return data

    # ── Checkout Form ─────────────────────────────────────────────────────────

    async def create_checkout_session(
        self,
        *,
        price_cents: int,
        currency: str,
        buyer_email: str,
        buyer_name: str,
        buyer_id: str,
        buyer_ip: str,
        basket_item_name: str,
        basket_item_id: str,
        callback_url: str,
        locale: str = "tr",
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Initialize a checkout form session. Returns token + payment page URL."""
        payload: dict[str, Any] = {
            "locale": locale,
            "conversationId": conversation_id or basket_item_id,
            "price": str(price_cents / 100),
            "paidPrice": str(price_cents / 100),
            "currency": currency,
            "basketId": basket_item_id,
            "paymentGroup": "SUBSCRIPTION",
            "callbackUrl": callback_url,
            "enabledInstallments": [1, 2, 3, 6, 9, 12],
            "buyer": {
                "id": buyer_id,
                "name": buyer_name.split(" ")[0] if buyer_name else "User",
                "surname": " ".join(buyer_name.split(" ")[1:]) if " " in buyer_name else "-",
                "email": buyer_email,
                "identityNumber": "00000000000",
                "registrationAddress": "TR",
                "ip": buyer_ip,
                "city": "Istanbul",
                "country": "Turkey",
            },
            "shippingAddress": {
                "contactName": buyer_name or "User",
                "city": "Istanbul",
                "country": "Turkey",
                "address": "TR",
            },
            "billingAddress": {
                "contactName": buyer_name or "User",
                "city": "Istanbul",
                "country": "Turkey",
                "address": "TR",
            },
            "basketItems": [
                {
                    "id": basket_item_id,
                    "name": basket_item_name,
                    "category1": "SaaS Subscription",
                    "itemType": "VIRTUAL",
                    "price": str(price_cents / 100),
                }
            ],
        }
        return await self._post("/payment/iyzipos/checkoutform/initialize/auth/ecom", payload)

    # ── Subscription management ───────────────────────────────────────────────

    async def cancel_subscription(self, subscription_reference_code: str) -> dict[str, Any]:
        payload = {
            "locale": "tr",
            "subscriptionReferenceCode": subscription_reference_code,
        }
        return await self._post("/v2/subscription/cancel", payload)

    async def get_subscription(self, subscription_reference_code: str) -> dict[str, Any]:
        payload = {
            "locale": "tr",
            "subscriptionReferenceCode": subscription_reference_code,
        }
        return await self._post("/v2/subscription/details", payload)

    # ── Webhook verification ──────────────────────────────────────────────────
    #
    # iyzico's V3 webhook signature (header X-IYZ-SIGNATURE-V3, see
    # https://docs.iyzico.com/en/advanced/webhook) is NOT an HMAC of the raw
    # request body. It's an HMAC-SHA256, hex-encoded, of specific payload
    # field *values* concatenated with no delimiter, keyed on the merchant's
    # own secretKey (the same IYZICO_SECRET_KEY used for API auth — iyzico
    # does not issue a separate webhook secret). The field set differs by
    # webhook shape:
    #
    #   subscription lifecycle: merchantId + secretKey + iyziEventType
    #     + subscriptionReferenceCode + orderReferenceCode + customerReferenceCode
    #   direct payment:         secretKey + iyziEventType + paymentId
    #     + paymentConversationId + status
    #   checkout form (HPP):    secretKey + iyziEventType + iyziPaymentId
    #     + token + paymentConversationId + status

    def verify_webhook_signature(self, payload: dict[str, Any], signature: str) -> bool:
        """Verify an iyzico X-IYZ-SIGNATURE-V3 webhook signature."""
        if not settings.IYZICO_SECRET_KEY:
            # Fail closed: an unconfigured secret must never be treated as a
            # passing signature check, in production or otherwise.
            return False

        event_type = payload.get("iyziEventType")
        if not event_type:
            return False

        if "subscriptionReferenceCode" in payload:
            if not settings.IYZICO_MERCHANT_ID:
                return False
            message = (
                settings.IYZICO_MERCHANT_ID
                + settings.IYZICO_SECRET_KEY
                + str(event_type)
                + str(payload.get("subscriptionReferenceCode", ""))
                + str(payload.get("orderReferenceCode", ""))
                + str(payload.get("customerReferenceCode", ""))
            )
        elif "token" in payload:
            message = (
                settings.IYZICO_SECRET_KEY
                + str(event_type)
                + str(payload.get("iyziPaymentId", ""))
                + str(payload.get("token", ""))
                + str(payload.get("paymentConversationId", ""))
                + str(payload.get("status", ""))
            )
        elif "paymentId" in payload:
            message = (
                settings.IYZICO_SECRET_KEY
                + str(event_type)
                + str(payload.get("paymentId", ""))
                + str(payload.get("paymentConversationId", ""))
                + str(payload.get("status", ""))
            )
        else:
            return False

        import hmac as _hmac

        expected = _hmac.new(
            settings.IYZICO_SECRET_KEY.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return _hmac.compare_digest(expected, signature)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.secret_key)


# Module-level singleton — re-reads config on access, safe for testing
iyzico_provider = IyzicoProvider()

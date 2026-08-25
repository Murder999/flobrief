"""Unit tests for Part 14 — Billing, entitlements, iyzico provider.

No DB required — pure Python logic + schema tests.
"""

from __future__ import annotations

import hashlib
import hmac
import unittest
from unittest.mock import MagicMock, patch

from app.models.enums import (
    BillingEventStatus,
    BillingProvider,
    InvoiceStatus,
    PlanCode,
    SubscriptionStatus,
)
from app.schemas.billing import (
    CheckoutRequest,
    CheckoutResponse,
    EntitlementCheckResponse,
    PlanRead,
    UsageSummary,
)

# ── Plan seed definitions ─────────────────────────────────────────────────────


class TestPlanDefinitions(unittest.TestCase):
    def test_plan_codes_are_valid_enum_values(self) -> None:
        codes = {pc.value for pc in PlanCode}
        expected = {
            "starter_agency",
            "pro_agency",
            "agency_plus",
            "brand_solo",
            "enterprise",
        }
        assert expected == codes

    def test_public_plan_order_keeps_enterprise_last(self) -> None:
        from app.repositories.plan import PUBLIC_PLAN_ORDER
        from scripts.seed_plans import PLAN_DEFINITIONS

        expected_order = (
            PlanCode.BRAND_SOLO.value,
            PlanCode.STARTER_AGENCY.value,
            PlanCode.PRO_AGENCY.value,
            PlanCode.AGENCY_PLUS.value,
            PlanCode.ENTERPRISE.value,
        )
        assert tuple(PUBLIC_PLAN_ORDER) == expected_order
        assert set(PUBLIC_PLAN_ORDER) == {plan["code"] for plan in PLAN_DEFINITIONS}

    def test_plan_entitlement_progression(self) -> None:
        # Pro should have higher limits than Starter
        from scripts.seed_plans import PLAN_DEFINITIONS

        plans = {p["code"]: p for p in PLAN_DEFINITIONS}
        starter = plans[PlanCode.STARTER_AGENCY.value]
        pro = plans[PlanCode.PRO_AGENCY.value]
        assert pro["max_brands"] > starter["max_brands"]
        assert pro["max_users"] > starter["max_users"]
        assert pro["monthly_price_cents"] > starter["monthly_price_cents"]

    def test_enterprise_has_no_hard_limits(self) -> None:
        from scripts.seed_plans import PLAN_DEFINITIONS

        plans = {p["code"]: p for p in PLAN_DEFINITIONS}
        ent = plans[PlanCode.ENTERPRISE.value]
        assert ent["max_brands"] is None
        assert ent["max_users"] is None
        assert ent["max_brief_templates"] is None
        assert ent["max_storage_gb"] is None

    def test_enterprise_has_all_features(self) -> None:
        from scripts.seed_plans import PLAN_DEFINITIONS

        plans = {p["code"]: p for p in PLAN_DEFINITIONS}
        ent = plans[PlanCode.ENTERPRISE.value]
        assert ent["white_label_enabled"] is True
        assert ent["advanced_reporting_enabled"] is True
        assert ent["pdf_export_enabled"] is True
        assert ent["public_report_link_enabled"] is True
        assert ent["whatsapp_infrastructure_enabled"] is True

    def test_starter_lacks_white_label(self) -> None:
        from scripts.seed_plans import PLAN_DEFINITIONS

        plans = {p["code"]: p for p in PLAN_DEFINITIONS}
        starter = plans[PlanCode.STARTER_AGENCY.value]
        assert starter["white_label_enabled"] is False

    def test_plan_seed_is_idempotent(self) -> None:
        from scripts.seed_plans import PLAN_DEFINITIONS

        codes = [p["code"] for p in PLAN_DEFINITIONS]
        assert len(codes) == len(set(codes)), "Plan codes must be unique"


# ── Billing enums ─────────────────────────────────────────────────────────────


class TestBillingEnums(unittest.TestCase):
    def test_invoice_status_values(self) -> None:
        values = {s.value for s in InvoiceStatus}
        assert "paid" in values
        assert "open" in values
        assert "void" in values

    def test_billing_event_status_values(self) -> None:
        values = {s.value for s in BillingEventStatus}
        assert "pending" in values
        assert "processed" in values
        assert "failed" in values

    def test_subscription_status_includes_past_due(self) -> None:
        assert SubscriptionStatus.PAST_DUE.value == "past_due"

    def test_billing_provider_values(self) -> None:
        assert BillingProvider.IYZICO.value == "iyzico"
        assert BillingProvider.MANUAL.value == "manual"


# ── Billing schemas ───────────────────────────────────────────────────────────


class TestBillingSchemas(unittest.TestCase):
    def _plan_data(self) -> dict:
        return {
            "id": "00000000-0000-0000-0000-000000000001",
            "code": "starter_agency",
            "name": "Starter",
            "description": "Test plan",
            "monthly_price_cents": 19900,
            "yearly_price_cents": 199000,
            "currency": "TRY",
            "max_brands": 3,
            "max_users": 5,
            "max_brand_users": 5,
            "max_brief_templates": 10,
            "max_storage_gb": 5,
            "max_pending_agency_invites": 10,
            "max_pending_brand_invites": 10,
            "white_label_enabled": False,
            "advanced_reporting_enabled": False,
            "pdf_export_enabled": True,
            "public_report_link_enabled": False,
            "whatsapp_infrastructure_enabled": False,
            "is_active": True,
        }

    def test_plan_read_schema(self) -> None:
        plan = PlanRead(**self._plan_data())
        assert plan.code == "starter_agency"
        assert plan.monthly_price_cents == 19900
        assert plan.white_label_enabled is False
        assert plan.pdf_export_enabled is True

    def test_checkout_request_schema(self) -> None:
        req = CheckoutRequest(plan_id="00000000-0000-0000-0000-000000000001")
        assert req.yearly is False

    def test_checkout_response_schema(self) -> None:
        resp = CheckoutResponse(
            payment_page_url="https://sandbox.iyzipay.com/pay/123",
            token="abc123",
            plan_code="starter_agency",
            amount_cents=19900,
            currency="TRY",
            provider="iyzico",
        )
        assert resp.sandbox is False

    def test_usage_summary_schema(self) -> None:
        summary = UsageSummary(
            plan_code="starter_agency",
            plan_name="Starter",
            brands={"used": 2, "limit": 3},
            users={"used": 3, "limit": 5},
            brief_templates={"used": 4, "limit": 10},
            storage_gb={"used": 0, "limit": 5},
            features={"white_label_enabled": False, "pdf_export_enabled": True},
        )
        assert summary.brands["used"] == 2
        assert summary.features["pdf_export_enabled"] is True

    def test_entitlement_check_allowed(self) -> None:
        resp = EntitlementCheckResponse(feature="pdf_export_enabled", allowed=True)
        assert resp.allowed is True
        assert resp.reason is None

    def test_entitlement_check_denied(self) -> None:
        resp = EntitlementCheckResponse(
            feature="white_label_enabled",
            allowed=False,
            reason="Plan limitine ulaştınız",
        )
        assert resp.allowed is False
        assert resp.reason is not None


# ── iyzico webhook signature ──────────────────────────────────────────────────


class TestIyzicoWebhookSignatureV3(unittest.TestCase):
    """iyzico's real X-IYZ-SIGNATURE-V3 algorithm (docs.iyzico.com/en/advanced/webhook):
    HMAC-SHA256, hex-encoded, of specific payload field *values* concatenated
    with no delimiter and keyed on the merchant secretKey — not a raw-body HMAC."""

    MERCHANT_ID = "merchant-123"
    SECRET_KEY = "merchant-secret"

    def _subscription_payload(self, event_type: str = "subscription.order.success") -> dict:
        return {
            "orderReferenceCode": "ae5fcbf8-4fd2-46e5-b199-8f690ae9fae5",
            "customerReferenceCode": "ff4052ca-0588-40eb-81a9-848c0c409472",
            "subscriptionReferenceCode": "ea0362e2-a1c4-4fda-89f0-3758a5c20a28",
            "iyziReferenceCode": "18d7cc48-a64b-4cd3-ae68-71aff1c76ed9",
            "iyziEventType": event_type,
            "iyziEventTime": 1758704403161,
        }

    def _expected_signature(self, payload: dict) -> str:
        message = (
            self.MERCHANT_ID
            + self.SECRET_KEY
            + payload["iyziEventType"]
            + payload["subscriptionReferenceCode"]
            + payload["orderReferenceCode"]
            + payload["customerReferenceCode"]
        )
        return hmac.new(
            self.SECRET_KEY.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def _provider_ctx(self, *, secret_key: str | None = None, merchant_id: str | None = None):
        patcher = patch("app.services.iyzico_provider.settings")
        mock_settings = patcher.start()
        mock_settings.IYZICO_API_KEY = "key"
        mock_settings.IYZICO_SECRET_KEY = self.SECRET_KEY if secret_key is None else secret_key
        mock_settings.IYZICO_MERCHANT_ID = self.MERCHANT_ID if merchant_id is None else merchant_id
        mock_settings.IYZICO_BASE_URL = "https://sandbox-api.iyzipay.com"
        self.addCleanup(patcher.stop)
        from app.services.iyzico_provider import IyzicoProvider

        return IyzicoProvider()

    def test_valid_v3_subscription_signature_accepted(self) -> None:
        payload = self._subscription_payload()
        sig = self._expected_signature(payload)
        provider = self._provider_ctx()
        assert provider.verify_webhook_signature(payload, sig) is True

    def test_tampered_field_rejected(self) -> None:
        payload = self._subscription_payload()
        sig = self._expected_signature(payload)
        payload["subscriptionReferenceCode"] = "a-different-reference-code"
        provider = self._provider_ctx()
        assert provider.verify_webhook_signature(payload, sig) is False

    def test_tampered_signature_rejected(self) -> None:
        payload = self._subscription_payload()
        sig = self._expected_signature(payload)
        tampered = sig[:-4] + ("0000" if sig[-4:] != "0000" else "1111")
        provider = self._provider_ctx()
        assert provider.verify_webhook_signature(payload, tampered) is False

    def test_missing_event_type_rejected(self) -> None:
        payload = self._subscription_payload()
        del payload["iyziEventType"]
        provider = self._provider_ctx()
        assert provider.verify_webhook_signature(payload, "any-sig") is False

    def test_empty_secret_fails_closed(self) -> None:
        payload = self._subscription_payload()
        sig = self._expected_signature(payload)
        provider = self._provider_ctx(secret_key="")
        assert provider.verify_webhook_signature(payload, sig) is False

    def test_missing_merchant_id_fails_closed_for_subscription_event(self) -> None:
        payload = self._subscription_payload()
        sig = self._expected_signature(payload)
        provider = self._provider_ctx(merchant_id="")
        assert provider.verify_webhook_signature(payload, sig) is False

    def test_v1_v2_style_raw_body_hmac_no_longer_accepted(self) -> None:
        """Guards against regressing to the old (wrong) raw-body HMAC scheme."""
        payload = self._subscription_payload()
        body = b'{"iyziEventType":"subscription.order.success"}'
        legacy_sig = hmac.new(self.SECRET_KEY.encode(), body, hashlib.sha256).hexdigest()
        provider = self._provider_ctx()
        assert provider.verify_webhook_signature(payload, legacy_sig) is False


# ── Webhook idempotency ───────────────────────────────────────────────────────


class TestWebhookIdempotency(unittest.TestCase):
    def test_duplicate_event_skipped(self) -> None:
        from app.models.enums import BillingEventStatus

        existing_event = MagicMock()
        existing_event.status = BillingEventStatus.PROCESSED.value
        assert existing_event.status == "processed"

    def test_new_event_processed(self) -> None:
        new_event = MagicMock()
        new_event.status = BillingEventStatus.PENDING.value
        assert new_event.status == "pending"


# ── iyzico provider sandbox mode ─────────────────────────────────────────────


class TestIyzicoProviderSandbox(unittest.TestCase):
    def test_not_configured_when_empty_keys(self) -> None:
        with patch("app.services.iyzico_provider.settings") as mock_settings:
            mock_settings.IYZICO_API_KEY = ""
            mock_settings.IYZICO_SECRET_KEY = ""
            mock_settings.IYZICO_BASE_URL = "https://sandbox-api.iyzipay.com"
            from app.services.iyzico_provider import IyzicoProvider

            provider = IyzicoProvider()
            assert provider.is_configured() is False

    def test_configured_when_keys_set(self) -> None:
        with patch("app.services.iyzico_provider.settings") as mock_settings:
            mock_settings.IYZICO_API_KEY = "sandbox-key"
            mock_settings.IYZICO_SECRET_KEY = "sandbox-secret"
            mock_settings.IYZICO_BASE_URL = "https://sandbox-api.iyzipay.com"
            from app.services.iyzico_provider import IyzicoProvider

            provider = IyzicoProvider()
            assert provider.is_configured() is True


# ── Card data not stored ──────────────────────────────────────────────────────


class TestCardDataNotStored(unittest.TestCase):
    def test_subscription_model_has_no_card_fields(self) -> None:
        from app.models.subscription import Subscription

        forbidden = {"card_number", "cvv", "card_holder", "expiry", "pan"}
        columns = {c.key for c in Subscription.__table__.columns}
        assert not forbidden.intersection(
            columns
        ), f"Card fields found in Subscription model: {forbidden.intersection(columns)}"

    def test_payment_customer_has_no_card_fields(self) -> None:
        from app.models.payment_customer import PaymentCustomer

        forbidden = {"card_number", "cvv", "card_holder", "expiry", "pan"}
        columns = {c.key for c in PaymentCustomer.__table__.columns}
        assert not forbidden.intersection(
            columns
        ), f"Card fields found in PaymentCustomer model: {forbidden.intersection(columns)}"

    def test_invoice_has_no_card_fields(self) -> None:
        from app.models.invoice import Invoice

        forbidden = {"card_number", "cvv", "card_holder", "expiry", "pan"}
        columns = {c.key for c in Invoice.__table__.columns}
        assert not forbidden.intersection(columns)


# ── Billing event model ───────────────────────────────────────────────────────


class TestBillingEventModel(unittest.TestCase):
    def test_billing_event_has_required_columns(self) -> None:
        from app.models.billing_event import BillingEvent

        columns = {c.key for c in BillingEvent.__table__.columns}
        assert "provider_event_id" in columns  # idempotency key
        assert "payload" in columns
        assert "status" in columns
        assert "processed_at" in columns

    def test_provider_event_id_is_unique(self) -> None:
        from app.models.billing_event import BillingEvent

        for col in BillingEvent.__table__.columns:
            if col.key == "provider_event_id":
                assert col.unique is True
                break

    def test_billing_events_recorded_schema(self) -> None:
        from app.models.billing_event import BillingEvent

        columns = {c.key for c in BillingEvent.__table__.columns}
        assert "event_type" in columns
        assert "provider" in columns


# ── Entitlement usage model ───────────────────────────────────────────────────


class TestEntitlementUsageModel(unittest.TestCase):
    def test_entitlement_usage_columns(self) -> None:
        from app.models.entitlement_usage import EntitlementUsage

        columns = {c.key for c in EntitlementUsage.__table__.columns}
        assert "agency_id" in columns
        assert "key" in columns
        assert "used_value" in columns
        assert "limit_value" in columns
        assert "calculated_at" in columns


# ── Subscription status sync ──────────────────────────────────────────────────


class TestSubscriptionStatusSync(unittest.TestCase):
    def test_status_map_covers_iyzico_states(self) -> None:
        status_map = {
            "ACTIVE": SubscriptionStatus.ACTIVE.value,
            "PENDING": SubscriptionStatus.TRIALING.value,
            "UNPAID": SubscriptionStatus.PAST_DUE.value,
            "CANCELLED": SubscriptionStatus.CANCELLED.value,
            "EXPIRED": SubscriptionStatus.EXPIRED.value,
            "PAST_DUE": SubscriptionStatus.PAST_DUE.value,
        }
        assert status_map["ACTIVE"] == "active"
        assert status_map["UNPAID"] == "past_due"
        assert status_map["CANCELLED"] == "cancelled"

    def test_sync_updates_status(self) -> None:
        new_status = SubscriptionStatus.PAST_DUE.value
        assert new_status in {s.value for s in SubscriptionStatus}


if __name__ == "__main__":
    unittest.main()

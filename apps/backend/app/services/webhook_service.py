"""WebhookService — iyzico webhook processing with idempotency."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BillingEventStatus, SubscriptionStatus
from app.repositories.billing import BillingEventRepository
from app.repositories.plan import PlanRepository
from app.repositories.subscription import SubscriptionRepository
from app.services.billing_service import BillingService
from app.services.iyzico_provider import IyzicoProvider

# The only subscription lifecycle events iyzico's webhook actually documents
# sending (docs.iyzico.com/en/advanced/webhook). Anything else is stored for
# audit via process_event() but not acted on.
_EVENT_STATUS_MAP: dict[str, str] = {
    "subscription.order.success": SubscriptionStatus.ACTIVE.value,
    "subscription.order.failure": SubscriptionStatus.PAST_DUE.value,
}


class WebhookService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.event_repo = BillingEventRepository(db)
        self.sub_repo = SubscriptionRepository(db)
        self.plan_repo = PlanRepository(db)
        self.billing_svc = BillingService(db)

    def verify_signature(self, payload: dict[str, Any], signature: str) -> bool:
        provider = IyzicoProvider()
        return provider.verify_webhook_signature(payload, signature)

    async def process_event(
        self,
        provider: str,
        event_type: str,
        provider_event_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        """Idempotent event processing — skips duplicate events by provider_event_id."""
        if provider_event_id:
            existing = await self.event_repo.get_by_provider_event_id(provider_event_id)
            if existing and existing.status == BillingEventStatus.PROCESSED.value:
                return  # Already processed — idempotent

        event = await self.event_repo.create(
            provider=provider,
            event_type=event_type,
            provider_event_id=provider_event_id,
            payload=payload,
            status=BillingEventStatus.PENDING.value,
        )
        await self.db.flush()

        try:
            await self._dispatch(event_type, payload)
            await self.event_repo.mark_processed(event)
        except Exception as exc:
            await self.event_repo.mark_failed(event, str(exc))
        finally:
            await self.db.commit()

    async def _dispatch(self, event_type: str, payload: dict[str, Any]) -> None:
        """Route an iyzico subscription webhook event to the billing service.

        Tenant identity is resolved via our own DB (provider_subscription_id
        lookup), never trusted from the webhook payload — a forged/replayed
        reference code in the JSON body can only ever match a subscription we
        actually issued, so it can't be used to alter another tenant's state.
        """
        mapped_status = _EVENT_STATUS_MAP.get(event_type)
        if not mapped_status:
            return

        sub_ref = payload.get("subscriptionReferenceCode")
        if not sub_ref:
            return

        subscription = await self.sub_repo.get_by_provider_subscription_id(sub_ref)
        if subscription is None or subscription.agency_id is None:
            # Unknown reference code, or a brand-scoped subscription (not yet
            # supported by sync_from_webhook) — nothing safe to act on.
            return

        invoice_data = None
        if event_type == "subscription.order.success":
            plan = await self.plan_repo.get_by_id(subscription.plan_id)
            invoice_data = {
                "provider_invoice_id": payload.get("iyziReferenceCode") or str(uuid.uuid4()),
                "amount_cents": plan.monthly_price_cents if plan else 0,
                "currency": plan.currency if plan else "TRY",
                "status": "paid",
                "hosted_invoice_url": None,
            }

        await self.billing_svc.sync_from_webhook(
            agency_id=subscription.agency_id,
            provider_subscription_id=sub_ref,
            new_status=mapped_status,
            invoice_data=invoice_data,
        )

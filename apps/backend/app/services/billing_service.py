"""BillingService — subscription lifecycle management.

Handles: current subscription read, checkout initiation, plan change,
cancellation, and subscription status sync from webhooks.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import BillingProvider, InvoiceStatus, SubscriptionStatus
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.repositories.billing import InvoiceRepository, PaymentCustomerRepository
from app.repositories.plan import PlanRepository
from app.repositories.subscription import SubscriptionRepository
from app.services.iyzico_provider import IyzicoError, IyzicoProvider

_403 = status.HTTP_403_FORBIDDEN
_404 = status.HTTP_404_NOT_FOUND
_409 = status.HTTP_409_CONFLICT


class BillingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.sub_repo = SubscriptionRepository(db)
        self.plan_repo = PlanRepository(db)
        self.pc_repo = PaymentCustomerRepository(db)
        self.inv_repo = InvoiceRepository(db)

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_subscription(self, agency_id: uuid.UUID) -> tuple[Subscription, Plan] | None:
        return await self.sub_repo.get_for_agency_with_plan(agency_id)

    async def list_invoices(self, agency_id: uuid.UUID) -> list:
        sub = await self.sub_repo.get_for_agency(agency_id)
        if sub is None:
            return []
        return await self.inv_repo.list_for_subscription(sub.id)

    # ── Checkout ──────────────────────────────────────────────────────────────

    async def create_checkout_session(
        self,
        agency_id: uuid.UUID,
        plan_id: uuid.UUID,
        buyer_email: str,
        buyer_name: str,
        buyer_id: str,
        buyer_ip: str,
        yearly: bool = False,
    ) -> dict:
        """Returns checkout token and payment page URL for iyzico checkout form."""
        plan = await self.plan_repo.get_by_id(plan_id)
        if plan is None:
            raise HTTPException(_404, "Plan bulunamadı")
        if not plan.is_active:
            raise HTTPException(_403, "Bu plan artık aktif değil")
        if plan.monthly_price_cents == 0:
            raise HTTPException(_403, "Enterprise plan için satış ekibiyle iletişime geçin")

        price_cents = plan.yearly_price_cents if yearly else plan.monthly_price_cents
        provider = IyzicoProvider()
        if not provider.is_configured():
            # Sandbox/dev mode: return simulated response without calling iyzico
            return {
                "payment_page_url": f"{settings.FRONTEND_URL}/billing/checkout-sandbox",
                "token": f"sandbox-{uuid.uuid4()}",
                "plan_code": plan.code,
                "amount_cents": price_cents,
                "currency": plan.currency,
                "provider": "manual",
                "sandbox": True,
            }

        callback_url = f"{settings.FRONTEND_URL}/dashboard/settings/billing?checkout=result"
        try:
            data = await provider.create_checkout_session(
                price_cents=price_cents,
                currency=plan.currency,
                buyer_email=buyer_email,
                buyer_name=buyer_name,
                buyer_id=buyer_id,
                buyer_ip=buyer_ip,
                basket_item_name=plan.name,
                basket_item_id=str(plan_id),
                callback_url=callback_url,
            )
        except IyzicoError as e:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"Ödeme başlatılamadı: {e.message}"
            ) from e

        return {
            "payment_page_url": data.get("paymentPageUrl"),
            "token": data.get("token"),
            "plan_code": plan.code,
            "amount_cents": price_cents,
            "currency": plan.currency,
            "provider": "iyzico",
        }

    # ── Plan change (platform admin override / internal) ──────────────────────

    async def change_plan(
        self,
        agency_id: uuid.UUID,
        new_plan_id: uuid.UUID,
        actor_notes: str = "",
    ) -> Subscription:
        sub = await self.sub_repo.get_for_agency(agency_id)
        new_plan = await self.plan_repo.get_by_id(new_plan_id)
        if new_plan is None:
            raise HTTPException(_404, "Plan bulunamadı")

        if sub is None:
            sub = await self.sub_repo.create(
                agency_id=agency_id,
                plan_id=new_plan_id,
                status=SubscriptionStatus.ACTIVE.value,
                billing_provider=BillingProvider.MANUAL.value,
                current_period_start=datetime.now(UTC),
            )
        else:
            sub.plan_id = new_plan_id
            self.db.add(sub)

        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    # ── Cancellation ──────────────────────────────────────────────────────────

    async def cancel_subscription(self, agency_id: uuid.UUID) -> Subscription:
        sub = await self.sub_repo.get_for_agency(agency_id)
        if sub is None:
            raise HTTPException(_404, "Aktif abonelik bulunamadı")

        if sub.provider_subscription_id and sub.billing_provider == BillingProvider.IYZICO.value:
            import contextlib

            provider = IyzicoProvider()
            if provider.is_configured():
                with contextlib.suppress(IyzicoError):
                    await provider.cancel_subscription(sub.provider_subscription_id)

        sub.status = SubscriptionStatus.CANCELLED.value
        sub.cancel_at_period_end = True
        self.db.add(sub)
        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    # ── Webhook sync ──────────────────────────────────────────────────────────

    async def sync_from_webhook(
        self,
        agency_id: uuid.UUID | None,
        provider_subscription_id: str | None,
        new_status: str,
        invoice_data: dict | None = None,
    ) -> None:
        """Update subscription status from webhook event."""
        if agency_id is None:
            return

        sub = await self.sub_repo.get_for_agency(agency_id)
        if sub is None:
            return

        if provider_subscription_id:
            sub.provider_subscription_id = provider_subscription_id

        if new_status in {s.value for s in SubscriptionStatus}:
            sub.status = new_status
        self.db.add(sub)

        if invoice_data:
            await self.inv_repo.create(
                subscription_id=sub.id,
                provider_invoice_id=invoice_data.get("provider_invoice_id"),
                amount_cents=invoice_data.get("amount_cents", 0),
                currency=invoice_data.get("currency", "TRY"),
                status=invoice_data.get("status", InvoiceStatus.PAID.value),
                period_start=invoice_data.get("period_start"),
                period_end=invoice_data.get("period_end"),
                hosted_invoice_url=invoice_data.get("hosted_invoice_url"),
            )

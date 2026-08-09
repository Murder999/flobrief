from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_event import BillingEvent
from app.models.entitlement_usage import EntitlementUsage
from app.models.invoice import Invoice
from app.models.payment_customer import PaymentCustomer


class PaymentCustomerRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_for_agency(self, agency_id: uuid.UUID, provider: str) -> PaymentCustomer | None:
        result = await self.db.execute(
            select(PaymentCustomer).where(
                PaymentCustomer.agency_id == agency_id,
                PaymentCustomer.provider == provider,
                PaymentCustomer.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs: object) -> PaymentCustomer:
        pc = PaymentCustomer(**kwargs)
        self.db.add(pc)
        await self.db.flush()
        await self.db.refresh(pc)
        return pc


class InvoiceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_subscription(
        self, subscription_id: uuid.UUID, limit: int = 20
    ) -> list[Invoice]:
        result = await self.db.execute(
            select(Invoice)
            .where(
                Invoice.subscription_id == subscription_id,
                Invoice.deleted_at.is_(None),
            )
            .order_by(Invoice.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, **kwargs: object) -> Invoice:
        inv = Invoice(**kwargs)
        self.db.add(inv)
        await self.db.flush()
        await self.db.refresh(inv)
        return inv


class BillingEventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_provider_event_id(self, provider_event_id: str) -> BillingEvent | None:
        result = await self.db.execute(
            select(BillingEvent).where(BillingEvent.provider_event_id == provider_event_id)
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs: object) -> BillingEvent:
        event = BillingEvent(**kwargs)
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def mark_processed(self, event: BillingEvent) -> None:
        from app.models.enums import BillingEventStatus

        event.status = BillingEventStatus.PROCESSED.value
        event.processed_at = datetime.now(UTC)
        self.db.add(event)

    async def mark_failed(self, event: BillingEvent, error: str) -> None:
        from app.models.enums import BillingEventStatus

        event.status = BillingEventStatus.FAILED.value
        event.error_message = error
        self.db.add(event)


class EntitlementUsageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_agency(self, agency_id: uuid.UUID) -> list[EntitlementUsage]:
        result = await self.db.execute(
            select(EntitlementUsage)
            .where(
                EntitlementUsage.agency_id == agency_id,
                EntitlementUsage.deleted_at.is_(None),
            )
            .order_by(EntitlementUsage.key.asc())
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        agency_id: uuid.UUID | None,
        key: str,
        used_value: int,
        limit_value: int | None,
    ) -> EntitlementUsage:
        existing = None
        if agency_id:
            result = await self.db.execute(
                select(EntitlementUsage).where(
                    EntitlementUsage.agency_id == agency_id,
                    EntitlementUsage.key == key,
                    EntitlementUsage.deleted_at.is_(None),
                )
            )
            existing = result.scalar_one_or_none()
        if existing:
            existing.used_value = used_value
            existing.limit_value = limit_value
            existing.calculated_at = datetime.now(UTC)
            self.db.add(existing)
            return existing
        eu = EntitlementUsage(
            agency_id=agency_id,
            key=key,
            used_value=used_value,
            limit_value=limit_value,
        )
        self.db.add(eu)
        await self.db.flush()
        await self.db.refresh(eu)
        return eu

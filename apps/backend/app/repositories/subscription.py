from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan
from app.models.subscription import Subscription


class SubscriptionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_for_agency(self, agency_id: uuid.UUID) -> Subscription | None:
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.agency_id == agency_id,
                Subscription.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_for_agency_with_plan(
        self, agency_id: uuid.UUID
    ) -> tuple[Subscription, Plan] | None:
        result = await self.db.execute(
            select(Subscription, Plan)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(
                Subscription.agency_id == agency_id,
                Subscription.deleted_at.is_(None),
            )
        )
        row = result.first()
        return (row[0], row[1]) if row else None

    async def get_by_id(self, subscription_id: uuid.UUID) -> Subscription | None:
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.id == subscription_id,
                Subscription.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_provider_subscription_id(
        self, provider_subscription_id: str
    ) -> Subscription | None:
        """Resolve the tenant subscription from a provider-issued reference
        code (e.g. iyzico's subscriptionReferenceCode). Used by webhook
        handlers so tenant identity comes from our own DB, never from a
        client-controlled webhook payload field."""
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.provider_subscription_id == provider_subscription_id,
                Subscription.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs: object) -> Subscription:
        sub = Subscription(**kwargs)
        self.db.add(sub)
        await self.db.flush()
        await self.db.refresh(sub)
        return sub

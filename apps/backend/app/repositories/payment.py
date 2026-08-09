from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting_connector import Payment


class PaymentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, payment_id: uuid.UUID, agency_id: uuid.UUID) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(
                Payment.id == payment_id,
                Payment.agency_id == agency_id,
                Payment.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_external_payment_id(
        self, agency_id: uuid.UUID, external_payment_id: str
    ) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(
                Payment.agency_id == agency_id,
                Payment.external_payment_id == external_payment_id,
                Payment.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_agency(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None = None,
        invoice_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Payment]:
        conditions = [
            Payment.agency_id == agency_id,
            Payment.deleted_at.is_(None),
        ]
        if brand_id is not None:
            conditions.append(Payment.brand_id == brand_id)
        if invoice_id is not None:
            conditions.append(Payment.invoice_id == invoice_id)
        result = await self.db.execute(
            select(Payment)
            .where(*conditions)
            .order_by(Payment.paid_at.desc(), Payment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def sum_paid_for_invoice(self, invoice_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(Payment).where(
                Payment.invoice_id == invoice_id,
                Payment.deleted_at.is_(None),
            )
        )
        return sum(p.amount_cents for p in result.scalars().all())

    async def create(self, data: dict) -> Payment:
        obj = Payment(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

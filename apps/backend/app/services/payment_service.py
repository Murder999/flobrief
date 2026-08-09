"""PaymentService (plan §3/§7): manual payment recording against a
`ClientInvoice`. Every recorded payment updates the invoice's
`amount_paid_cents` and recomputes its status —
`partially_paid` when `0 < amount_paid_cents < total_cents`, `paid` when
`amount_paid_cents >= total_cents`. A payment that would push the invoice
past its `total_cents` is rejected unless the caller explicitly passes
`allow_overpayment=True`; a payment against a `cancelled` invoice, or one
carrying an `external_payment_id` that already exists for this agency, is
always rejected regardless of that flag."""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.accounting_connector import Payment
from app.models.client_invoice import ClientInvoice
from app.models.enums import ClientInvoiceStatus, PaymentSource
from app.repositories.client_invoice import ClientInvoiceRepository
from app.repositories.payment import PaymentRepository
from app.schemas.payment import PaymentCreate


class PaymentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = PaymentRepository(db)
        self._invoice_repo = ClientInvoiceRepository(db)

    async def record_payment(
        self, agency_id: uuid.UUID, actor_id: uuid.UUID, data: PaymentCreate
    ) -> Payment:
        invoice: ClientInvoice | None = None
        if data.invoice_id is not None:
            invoice = await self._invoice_repo.get_by_id(data.invoice_id, agency_id)
            if invoice is None:
                raise NotFoundError("Fatura", str(data.invoice_id))
            if invoice.brand_id != data.brand_id:
                raise ValidationError("Fatura seçilen markaya ait değil")
            if invoice.status == ClientInvoiceStatus.CANCELLED.value:
                raise ConflictError("İptal edilmiş bir faturaya ödeme kaydedilemez")

            remaining = invoice.total_cents - invoice.amount_paid_cents
            if data.amount_cents > remaining and not data.allow_overpayment:
                raise ValidationError(
                    "Ödeme tutarı faturanın kalan bakiyesini aşıyor "
                    "(fazla ödeme için allow_overpayment=true gönderin)"
                )

        if data.external_payment_id is not None:
            duplicate = await self._repo.get_by_external_payment_id(
                agency_id, data.external_payment_id
            )
            if duplicate is not None:
                raise ConflictError("Bu external_payment_id ile zaten bir ödeme kayıtlı")

        payment = await self._repo.create(
            {
                "agency_id": agency_id,
                "brand_id": data.brand_id,
                "invoice_id": data.invoice_id,
                "amount_cents": data.amount_cents,
                "currency": data.currency,
                "payment_method": data.payment_method,
                "paid_at": data.paid_at,
                "external_payment_id": data.external_payment_id,
                "source": PaymentSource.MANUAL.value,
                "notes": data.notes,
                "recorded_by_id": actor_id,
            }
        )

        fully_paid = False
        if invoice is not None:
            new_paid = invoice.amount_paid_cents + data.amount_cents
            update_data: dict = {"amount_paid_cents": new_paid}
            if new_paid >= invoice.total_cents:
                update_data["status"] = ClientInvoiceStatus.PAID.value
                update_data["paid_at"] = datetime.now(UTC)
                fully_paid = True
            elif new_paid > 0:
                update_data["status"] = ClientInvoiceStatus.PARTIALLY_PAID.value
            await self._invoice_repo.update(invoice, update_data)

        await self._db.commit()
        await self._db.refresh(payment)

        if invoice is not None and fully_paid:
            with contextlib.suppress(Exception):
                await self._notify_payment_received(invoice, payment)

        return payment

    async def _notify_payment_received(self, invoice: ClientInvoice, payment: Payment) -> None:
        """Notify agency roles holding invoice:view that a client payment
        fully settled this invoice — narrowed to that permission the same
        way finance_capacity_scheduler resolves invoice:approve recipients.
        Never the brand (client-facing "invoice paid" confirmation is out of
        scope here) and never a cost/rate figure — only the payment amount
        the client themselves already sent."""
        from sqlalchemy import select

        from app.core.rbac import Permission, get_permissions_for_agency_role
        from app.models.agency_member import AgencyMember
        from app.models.enums import AgencyMemberStatus, NotificationEventType
        from app.services.notification_dispatcher import NotificationDispatcher

        rows = await self._db.execute(
            select(AgencyMember.user_id, AgencyMember.role).where(
                AgencyMember.agency_id == invoice.agency_id,
                AgencyMember.deleted_at.is_(None),
                AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
            )
        )
        recipient_ids = [
            row.user_id
            for row in rows
            if Permission.INVOICE_VIEW in get_permissions_for_agency_role(row.role)
        ]
        if not recipient_ids:
            return

        await NotificationDispatcher(self._db).emit(
            NotificationEventType.INVOICE_PAYMENT_RECEIVED.value,
            payload={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "payment_id": str(payment.id),
                "amount_cents": payment.amount_cents,
                "currency": payment.currency,
                "summary": f"{invoice.invoice_number} numaralı fatura için ödeme alındı.",
            },
            agency_id=invoice.agency_id,
            brand_id=invoice.brand_id,
            actor_user_id=None,
            recipient_ids=recipient_ids,
        )
        await self._db.commit()

    async def list_for_agency(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None = None,
        invoice_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Payment]:
        return await self._repo.list_for_agency(agency_id, brand_id, invoice_id, limit, offset)

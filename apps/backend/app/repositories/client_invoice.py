from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_invoice import ClientInvoice, ClientInvoiceLine


class ClientInvoiceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, invoice_id: uuid.UUID, agency_id: uuid.UUID) -> ClientInvoice | None:
        result = await self.db.execute(
            select(ClientInvoice).where(
                ClientInvoice.id == invoice_id,
                ClientInvoice.agency_id == agency_id,
                ClientInvoice.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_agency(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ClientInvoice]:
        conditions = [
            ClientInvoice.agency_id == agency_id,
            ClientInvoice.deleted_at.is_(None),
        ]
        if brand_id is not None:
            conditions.append(ClientInvoice.brand_id == brand_id)
        if status is not None:
            conditions.append(ClientInvoice.status == status)
        result = await self.db.execute(
            select(ClientInvoice)
            .where(*conditions)
            .order_by(ClientInvoice.issue_date.desc(), ClientInvoice.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, data: dict) -> ClientInvoice:
        obj = ClientInvoice(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, obj: ClientInvoice, data: dict) -> ClientInvoice:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        return obj

    async def add_line(self, data: dict) -> ClientInvoiceLine:
        line = ClientInvoiceLine(**data)
        self.db.add(line)
        await self.db.flush()
        return line

    async def list_lines(self, invoice_id: uuid.UUID) -> list[ClientInvoiceLine]:
        result = await self.db.execute(
            select(ClientInvoiceLine)
            .where(
                ClientInvoiceLine.invoice_id == invoice_id,
                ClientInvoiceLine.deleted_at.is_(None),
            )
            .order_by(ClientInvoiceLine.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_line(self, line_id: uuid.UUID, invoice_id: uuid.UUID) -> ClientInvoiceLine | None:
        result = await self.db.execute(
            select(ClientInvoiceLine).where(
                ClientInvoiceLine.id == line_id,
                ClientInvoiceLine.invoice_id == invoice_id,
                ClientInvoiceLine.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def soft_delete_line(self, line: ClientInvoiceLine) -> None:
        line.soft_delete()
        await self.db.flush()

    async def list_visible_for_brand(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID,
        exclude_statuses: tuple[str, ...],
        limit: int = 50,
        offset: int = 0,
    ) -> list[ClientInvoice]:
        """Brand-portal read (plan §9): only invoices that have actually
        left draft/approval-pending state (and aren't cancelled) are ever
        visible to the brand — a brand user must never see an agency's
        internal in-progress drafting."""
        result = await self.db.execute(
            select(ClientInvoice)
            .where(
                ClientInvoice.agency_id == agency_id,
                ClientInvoice.brand_id == brand_id,
                ClientInvoice.deleted_at.is_(None),
                ClientInvoice.status.not_in(exclude_statuses),
            )
            .order_by(ClientInvoice.issue_date.desc(), ClientInvoice.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_visible_for_brand(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID,
        invoice_id: uuid.UUID,
        exclude_statuses: tuple[str, ...],
    ) -> ClientInvoice | None:
        result = await self.db.execute(
            select(ClientInvoice).where(
                ClientInvoice.id == invoice_id,
                ClientInvoice.agency_id == agency_id,
                ClientInvoice.brand_id == brand_id,
                ClientInvoice.deleted_at.is_(None),
                ClientInvoice.status.not_in(exclude_statuses),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_period(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None,
        start: date | None,
        end: date | None,
        exclude_statuses: tuple[str, ...] = (),
    ) -> list[ClientInvoice]:
        """All (unpaginated) invoices matching the filters — used by
        `ProfitabilityService` for period-based revenue aggregation, where a
        default page size would silently under-count. Filters on
        `issue_date`, the date a `ClientInvoice` is considered "issued" for
        revenue-recognition purposes in this codebase."""
        conditions = [
            ClientInvoice.agency_id == agency_id,
            ClientInvoice.deleted_at.is_(None),
        ]
        if brand_id is not None:
            conditions.append(ClientInvoice.brand_id == brand_id)
        if start is not None:
            conditions.append(ClientInvoice.issue_date >= start)
        if end is not None:
            conditions.append(ClientInvoice.issue_date <= end)
        if exclude_statuses:
            conditions.append(ClientInvoice.status.not_in(exclude_statuses))
        result = await self.db.execute(
            select(ClientInvoice).where(*conditions).order_by(ClientInvoice.issue_date.asc())
        )
        return list(result.scalars().all())

    async def list_lines_for_invoices(
        self, invoice_ids: list[uuid.UUID]
    ) -> list[ClientInvoiceLine]:
        """Batch line lookup across many invoices at once (avoids N+1 when
        aggregating profitability across a brand/agency's whole invoice
        set)."""
        if not invoice_ids:
            return []
        result = await self.db.execute(
            select(ClientInvoiceLine).where(
                ClientInvoiceLine.invoice_id.in_(invoice_ids),
                ClientInvoiceLine.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def is_time_entry_already_invoiced(self, time_entry_id: uuid.UUID) -> bool:
        """Defense-in-depth read mirroring the partial unique index on
        `client_invoice_lines(source_id) WHERE source_type='time_entry'`."""
        result = await self.db.execute(
            select(ClientInvoiceLine.id).where(
                ClientInvoiceLine.source_type == "time_entry",
                ClientInvoiceLine.source_id == time_entry_id,
                ClientInvoiceLine.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None

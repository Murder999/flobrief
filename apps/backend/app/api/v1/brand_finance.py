"""Brand-portal invoice view (plan §9, closes the Phase-4 gap): a
read-only list + PDF export of the calling brand's own, already-sent
invoices. Gated by `get_brand_portal_context` — NOT `require_permission`/
`WorkspaceContext` — brand users are a completely separate auth context
from agency workspace members (matches `brand_portal.py`'s split).

Visibility rule: only invoices whose status has left `draft`/
`pending_approval` and isn't `cancelled` are ever returned — an agency's
in-progress drafting must never be visible to the brand it concerns.
"""

from __future__ import annotations

import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.brand_portal_auth import BrandPortalContext, get_brand_portal_context
from app.db.session import get_db
from app.models.agency import Agency
from app.models.enums import ClientInvoiceStatus
from app.repositories.client_invoice import ClientInvoiceRepository
from app.schemas.brand_finance import BrandInvoiceLineRead, BrandInvoiceRead, BrandInvoiceWithLines
from app.services.invoice_pdf_service import InvoicePdfService

brand_finance_router = APIRouter(prefix="/brand-portal", tags=["brand-portal-finance"])

_HIDDEN_STATUSES = (
    ClientInvoiceStatus.DRAFT.value,
    ClientInvoiceStatus.PENDING_APPROVAL.value,
    ClientInvoiceStatus.CANCELLED.value,
)


@brand_finance_router.get("/invoices", response_model=list[BrandInvoiceRead])
async def list_brand_invoices(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[BrandInvoiceRead]:
    items = await ClientInvoiceRepository(db).list_visible_for_brand(
        ctx.brand.agency_id, ctx.brand.id, _HIDDEN_STATUSES, limit, offset
    )
    return [BrandInvoiceRead.model_validate(i) for i in items]


@brand_finance_router.get("/invoices/{invoice_id}", response_model=BrandInvoiceWithLines)
async def get_brand_invoice(
    invoice_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> BrandInvoiceWithLines:
    repo = ClientInvoiceRepository(db)
    invoice = await repo.get_visible_for_brand(
        ctx.brand.agency_id, ctx.brand.id, invoice_id, _HIDDEN_STATUSES
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura bulunamadı")

    lines = await repo.list_lines(invoice.id)
    return BrandInvoiceWithLines(
        **BrandInvoiceRead.model_validate(invoice).model_dump(),
        lines=[BrandInvoiceLineRead.model_validate(line) for line in lines],
    )


@brand_finance_router.get("/invoices/{invoice_id}/pdf")
async def download_brand_invoice_pdf(
    invoice_id: uuid.UUID,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    repo = ClientInvoiceRepository(db)
    invoice = await repo.get_visible_for_brand(
        ctx.brand.agency_id, ctx.brand.id, invoice_id, _HIDDEN_STATUSES
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura bulunamadı")

    lines = await repo.list_lines(invoice.id)
    agency = await db.get(Agency, ctx.brand.agency_id)
    agency_name = agency.name if agency is not None else "-"
    pdf_bytes = InvoicePdfService.build_pdf_bytes(
        invoice, lines, agency_name=agency_name, brand_name=ctx.brand.name
    )
    filename = f"fatura-{invoice.invoice_number}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

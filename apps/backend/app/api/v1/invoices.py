"""Client-invoicing endpoints (plan §9): billable-time selection, draft
generation/editing, lifecycle transitions (approve/send/void), and PDF/CSV
export. Every mutating endpoint writes an `ActivityLogRepository` row whose
`meta` carries invoice_number/status-transition context only — never
cost-rate/internal-margin figures (plan §7/§12)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, require_permission
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.rbac import Permission
from app.db.session import get_db
from app.repositories.activity import ActivityLogRepository
from app.repositories.brand import BrandRepository
from app.schemas.client_invoice import (
    BillableTimeEntryRead,
    ClientInvoiceDraftCreate,
    ClientInvoiceLineRead,
    ClientInvoiceRead,
    ClientInvoiceUpdate,
    ManualInvoiceLineInput,
)
from app.services.client_invoice_service import ClientInvoiceService
from app.services.invoice_pdf_service import InvoicePdfService
from app.services.retainer_service import RetainerService

invoice_router = APIRouter(prefix="/finance", tags=["finance-invoices"])


def _svc(db: AsyncSession = Depends(get_db)) -> ClientInvoiceService:
    return ClientInvoiceService(db)


def _to_http(err: Exception) -> HTTPException:
    if isinstance(err, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err.message)
    if isinstance(err, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err.message)
    if isinstance(err, ValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err.message)
    raise err


async def _with_lines(
    svc: ClientInvoiceService, agency_id: uuid.UUID, invoice_id: uuid.UUID
) -> dict:
    try:
        invoice, lines = await svc.get_with_lines(agency_id, invoice_id)
    except (NotFoundError, ConflictError, ValidationError) as err:
        raise _to_http(err) from err
    return {
        **ClientInvoiceRead.model_validate(invoice).model_dump(),
        "lines": [ClientInvoiceLineRead.model_validate(line) for line in lines],
    }


# ── Billable time ───────────────────────────────────────────────────────────


@invoice_router.get("/billable-time", response_model=list[BillableTimeEntryRead])
async def list_billable_time(
    brand_id: uuid.UUID = Query(...),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.BILLING_TIME_VIEW)),
    svc: ClientInvoiceService = Depends(_svc),
) -> list[BillableTimeEntryRead]:
    entries = await svc.list_billable_time_entries(workspace.agency.id, brand_id, start, end)
    return [BillableTimeEntryRead.model_validate(e) for e in entries]


# ── Draft generation ────────────────────────────────────────────────────────


@invoice_router.post("/invoices/draft", response_model=dict, status_code=201)
async def create_draft_invoice(
    data: ClientInvoiceDraftCreate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.INVOICE_CREATE)),
    db: AsyncSession = Depends(get_db),
    svc: ClientInvoiceService = Depends(_svc),
) -> dict:
    try:
        invoice = await svc.generate_draft(workspace.agency.id, workspace.user.id, data)
    except (NotFoundError, ConflictError, ValidationError) as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="client_invoice.draft_created",
        entity_type="client_invoice",
        entity_id=invoice.id,
        agency_id=workspace.agency.id,
        brand_id=invoice.brand_id,
        actor_user_id=workspace.user.id,
        meta={
            "invoice_number": invoice.invoice_number,
            "status": invoice.status,
            "total_cents": invoice.total_cents,
            "currency": invoice.currency,
        },
    )
    await db.commit()
    return await _with_lines(svc, workspace.agency.id, invoice.id)


@invoice_router.post("/invoices/{invoice_id}/lines", response_model=dict, status_code=201)
async def add_manual_line(
    invoice_id: uuid.UUID,
    data: ManualInvoiceLineInput,
    workspace: WorkspaceContext = Depends(require_permission(Permission.INVOICE_CREATE)),
    db: AsyncSession = Depends(get_db),
    svc: ClientInvoiceService = Depends(_svc),
) -> dict:
    try:
        invoice = await svc.add_manual_line(workspace.agency.id, invoice_id, data)
    except (NotFoundError, ConflictError, ValidationError) as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="client_invoice.line_added",
        entity_type="client_invoice",
        entity_id=invoice.id,
        agency_id=workspace.agency.id,
        brand_id=invoice.brand_id,
        actor_user_id=workspace.user.id,
        meta={"invoice_number": invoice.invoice_number, "source_type": data.source_type},
    )
    await db.commit()
    return await _with_lines(svc, workspace.agency.id, invoice.id)


@invoice_router.delete("/invoices/{invoice_id}/lines/{line_id}", response_model=dict)
async def remove_line(
    invoice_id: uuid.UUID,
    line_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.INVOICE_CREATE)),
    db: AsyncSession = Depends(get_db),
    svc: ClientInvoiceService = Depends(_svc),
) -> dict:
    try:
        invoice = await svc.remove_line(workspace.agency.id, invoice_id, line_id)
    except (NotFoundError, ConflictError, ValidationError) as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="client_invoice.line_removed",
        entity_type="client_invoice",
        entity_id=invoice.id,
        agency_id=workspace.agency.id,
        brand_id=invoice.brand_id,
        actor_user_id=workspace.user.id,
        meta={"invoice_number": invoice.invoice_number, "line_id": str(line_id)},
    )
    await db.commit()
    return await _with_lines(svc, workspace.agency.id, invoice.id)


# ── Listing / detail / patch ────────────────────────────────────────────────


@invoice_router.get("/invoices", response_model=list[ClientInvoiceRead])
async def list_invoices(
    brand_id: uuid.UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = 50,
    offset: int = 0,
    workspace: WorkspaceContext = Depends(require_permission(Permission.INVOICE_VIEW)),
    svc: ClientInvoiceService = Depends(_svc),
) -> list[ClientInvoiceRead]:
    items = await svc.list_for_agency(workspace.agency.id, brand_id, status_filter, limit, offset)
    return [ClientInvoiceRead.model_validate(i) for i in items]


@invoice_router.get("/invoices/{invoice_id}", response_model=dict)
async def get_invoice(
    invoice_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.INVOICE_VIEW)),
    svc: ClientInvoiceService = Depends(_svc),
) -> dict:
    return await _with_lines(svc, workspace.agency.id, invoice_id)


@invoice_router.patch("/invoices/{invoice_id}", response_model=dict)
async def update_invoice(
    invoice_id: uuid.UUID,
    data: ClientInvoiceUpdate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.INVOICE_CREATE)),
    db: AsyncSession = Depends(get_db),
    svc: ClientInvoiceService = Depends(_svc),
) -> dict:
    try:
        invoice = await svc.update(workspace.agency.id, invoice_id, data)
    except (NotFoundError, ConflictError, ValidationError) as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="client_invoice.updated",
        entity_type="client_invoice",
        entity_id=invoice.id,
        agency_id=workspace.agency.id,
        brand_id=invoice.brand_id,
        actor_user_id=workspace.user.id,
        meta={"fields": list(data.model_dump(exclude_unset=True).keys())},
    )
    await db.commit()
    return await _with_lines(svc, workspace.agency.id, invoice.id)


# ── Lifecycle transitions ───────────────────────────────────────────────────


@invoice_router.post("/invoices/{invoice_id}/approve", response_model=dict)
async def approve_invoice(
    invoice_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.INVOICE_APPROVE)),
    db: AsyncSession = Depends(get_db),
    svc: ClientInvoiceService = Depends(_svc),
) -> dict:
    try:
        invoice = await svc.approve(workspace.agency.id, invoice_id, workspace.user.id)
    except (NotFoundError, ConflictError, ValidationError) as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="client_invoice.approved",
        entity_type="client_invoice",
        entity_id=invoice.id,
        agency_id=workspace.agency.id,
        brand_id=invoice.brand_id,
        actor_user_id=workspace.user.id,
        meta={"invoice_number": invoice.invoice_number, "status": invoice.status},
    )
    await db.commit()
    return await _with_lines(svc, workspace.agency.id, invoice.id)


@invoice_router.post("/invoices/{invoice_id}/send", response_model=dict)
async def send_invoice(
    invoice_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.INVOICE_APPROVE)),
    db: AsyncSession = Depends(get_db),
    svc: ClientInvoiceService = Depends(_svc),
) -> dict:
    try:
        invoice = await svc.send(workspace.agency.id, invoice_id)
    except (NotFoundError, ConflictError, ValidationError) as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="client_invoice.sent",
        entity_type="client_invoice",
        entity_id=invoice.id,
        agency_id=workspace.agency.id,
        brand_id=invoice.brand_id,
        actor_user_id=workspace.user.id,
        meta={"invoice_number": invoice.invoice_number, "status": invoice.status},
    )
    await db.commit()
    return await _with_lines(svc, workspace.agency.id, invoice.id)


@invoice_router.post("/invoices/{invoice_id}/void", response_model=dict)
async def void_invoice(
    invoice_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.INVOICE_VOID)),
    db: AsyncSession = Depends(get_db),
    svc: ClientInvoiceService = Depends(_svc),
) -> dict:
    try:
        invoice = await svc.void(workspace.agency.id, invoice_id)
    except (NotFoundError, ConflictError, ValidationError) as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="client_invoice.voided",
        entity_type="client_invoice",
        entity_id=invoice.id,
        agency_id=workspace.agency.id,
        brand_id=invoice.brand_id,
        actor_user_id=workspace.user.id,
        meta={"invoice_number": invoice.invoice_number, "status": invoice.status},
    )
    await db.commit()
    return await _with_lines(svc, workspace.agency.id, invoice.id)


# ── Export ───────────────────────────────────────────────────────────────────


@invoice_router.get("/invoices/{invoice_id}/pdf")
async def export_invoice_pdf(
    invoice_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.INVOICE_VIEW)),
    db: AsyncSession = Depends(get_db),
    svc: ClientInvoiceService = Depends(_svc),
) -> StreamingResponse:
    try:
        invoice, lines = await svc.get_with_lines(workspace.agency.id, invoice_id)
    except (NotFoundError, ConflictError, ValidationError) as err:
        raise _to_http(err) from err

    brand = await BrandRepository(db).get_by_id_and_agency(invoice.brand_id, workspace.agency.id)
    brand_name = brand.name if brand is not None else "-"
    pdf_bytes = InvoicePdfService.build_pdf_bytes(
        invoice, lines, agency_name=workspace.agency.name, brand_name=brand_name
    )
    filename = f"fatura-{invoice.invoice_number}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@invoice_router.get("/invoices/{invoice_id}/csv")
async def export_invoice_csv(
    invoice_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.INVOICE_VIEW)),
    svc: ClientInvoiceService = Depends(_svc),
) -> StreamingResponse:
    try:
        csv_bytes = await svc.export_csv(workspace.agency.id, invoice_id)
    except (NotFoundError, ConflictError, ValidationError) as err:
        raise _to_http(err) from err

    filename = f"fatura-{invoice_id}.csv"
    return StreamingResponse(
        BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Retainers (read-only summary; RetainerService, plan §3/§7) ─────────────


@invoice_router.get("/retainers/{brand_id}", response_model=dict)
async def get_retainer_summary(
    brand_id: uuid.UUID,
    as_of: date | None = Query(None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.BILLING_TIME_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        summary = await RetainerService(db).get_current_period_summary(
            workspace.agency.id, brand_id, as_of
        )
    except (NotFoundError, ValidationError) as err:
        raise _to_http(err) from err
    return {
        "period_start": summary.period_start,
        "period_end": summary.period_end,
        "included_minutes": summary.included_minutes,
        "rolled_over_minutes": summary.rolled_over_minutes,
        "used_minutes": summary.used_minutes,
        "remaining_minutes": summary.remaining_minutes,
        "overage_minutes": summary.overage_minutes,
        "overage_cost_cents": summary.overage_cost_cents,
        "currency": summary.currency,
    }

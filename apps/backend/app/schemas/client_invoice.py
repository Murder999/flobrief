from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ClientInvoiceDocumentType

_VALID_DOCUMENT_TYPES = {t.value for t in ClientInvoiceDocumentType}


class ManualInvoiceLineInput(BaseModel):
    """Explicit field allowlist for a non-time-entry line (fixed_fee/
    per_item/manual) added at draft-generation or draft-edit time — never
    accepts `source_id` for anything but `deliverable` (validated by the
    service, not this schema, since the valid ids differ per source_type)."""

    source_type: str = Field(default="manual")
    source_id: uuid.UUID | None = None
    description: str = Field(..., min_length=1, max_length=2000)
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=20)
    unit_price_cents: int = Field(..., ge=0)
    tax_rate_bps: int = Field(0, ge=0, le=10000)
    discount_cents: int = Field(0, ge=0)


class ClientInvoiceDraftCreate(BaseModel):
    brand_id: uuid.UUID
    time_entry_ids: list[uuid.UUID] = Field(default_factory=list)
    include_fixed_fee: bool = False
    manual_lines: list[ManualInvoiceLineInput] = Field(default_factory=list)
    document_type: str = Field(default=ClientInvoiceDocumentType.DRAFT_INVOICE.value)
    issue_date: date | None = None
    due_date: date | None = None
    service_period_start: date | None = None
    service_period_end: date | None = None
    notes: str | None = Field(None, max_length=4000)

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        if v not in _VALID_DOCUMENT_TYPES:
            raise ValueError(f"Geçersiz belge türü: {v}")
        return v


class ClientInvoiceUpdate(BaseModel):
    """Only draft-stage, non-money-integrity fields are patchable directly —
    line/total changes always go through `update_draft_lines` so totals stay
    internally consistent."""

    notes: str | None = Field(None, max_length=4000)
    due_date: date | None = None
    document_type: str | None = None
    billing_contact_name: str | None = None
    billing_contact_email: str | None = None

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_DOCUMENT_TYPES:
            raise ValueError(f"Geçersiz belge türü: {v}")
        return v


class ClientInvoiceLineRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    invoice_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID | None
    description: str
    quantity: float
    unit: str
    unit_price_cents: int
    tax_rate_bps: int
    discount_cents: int
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    service_period_start: date | None
    service_period_end: date | None
    # Deliberately excludes billing_rate_snapshot_cents/cost_rate_snapshot_cents
    # from the default read shape — internal cost data never leaves this
    # module's own service layer / PDF-exclusion boundary.


class ClientInvoiceRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID
    commercial_terms_id: uuid.UUID | None
    invoice_number: str
    external_invoice_id: str | None
    document_type: str
    issue_date: date
    due_date: date
    service_period_start: date | None
    service_period_end: date | None
    currency: str
    subtotal_cents: int
    discount_cents: int
    tax_cents: int
    total_cents: int
    amount_paid_cents: int
    status: str
    notes: str | None
    billing_contact_name: str | None
    billing_contact_email: str | None
    billing_address: dict | None
    tax_office: str | None
    tax_number: str | None
    sent_at: datetime | None
    paid_at: datetime | None
    cancelled_at: datetime | None
    created_by_id: uuid.UUID | None
    approved_by_id: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ClientInvoiceWithLines(ClientInvoiceRead):
    lines: list[ClientInvoiceLineRead] = Field(default_factory=list)


class BillableTimeEntryRead(BaseModel):
    """Read shape for `GET /finance/billable-time` — deliberately excludes
    `cost_rate_snapshot_cents` (always null pre-invoicing anyway) and any
    internal-margin figure."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    brief_id: uuid.UUID | None
    category: str
    description: str | None
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    locked: bool

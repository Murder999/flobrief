"""Brand-portal invoice read schema (plan §9, the Phase-4 gap closed in
Phase 5). Deliberately a SEPARATE, minimal schema from the internal
`ClientInvoiceRead` — it exists purely to guarantee, by construction, that
no internal margin/cost field (`cost_rate_snapshot_cents`,
`billing_rate_snapshot_cents`, or any future internal-only column) or
agency-internal bookkeeping field (`commercial_terms_id`, `created_by_id`,
`approved_by_id`) can ever leak onto the brand-portal invoice view, even if
a future edit to `ClientInvoiceRead` accidentally adds one."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class BrandInvoiceRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    invoice_number: str
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
    tax_office: str | None
    tax_number: str | None
    sent_at: datetime | None
    paid_at: datetime | None


class BrandInvoiceLineRead(BaseModel):
    """One billable line as shown to the brand. Deliberately a separate,
    even-more-minimal schema than the agency-side `ClientInvoiceLineRead` —
    no `invoice_id`/`source_type`/`source_id` (agency-internal bookkeeping),
    and by construction no `billing_rate_snapshot_cents`/
    `cost_rate_snapshot_cents` (see this module's docstring)."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
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


class BrandInvoiceWithLines(BrandInvoiceRead):
    lines: list[BrandInvoiceLineRead] = []

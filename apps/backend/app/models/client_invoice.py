from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.models.enums import ClientInvoiceDocumentType, ClientInvoiceStatus

_VALID_DOCUMENT_TYPES = {t.value for t in ClientInvoiceDocumentType}


class ClientInvoice(BaseModel):
    """An agency's bill to one of its brand clients — deliberately separate
    from `app.models.invoice.Invoice` (Flobrief's own SaaS subscription
    billing via iyzico, plan §1). `document_type` is constrained at the DB
    level to `draft_invoice`/`proforma` only — this system never issues a
    legally-valid Turkish e-invoice (`e-fatura`) and must never claim to.

    Billing/tax identity (`billing_contact_*`, `tax_office`, `tax_number`,
    `billing_address`) is snapshotted from `CommercialTerms`/`Brand` at
    creation time and never silently reflows if the brand's billing info
    changes later — each issued invoice reflects what was true when it was
    issued.

    Invoice numbering is a per-agency sequence (`AgencySettings.invoice_number_seq`)
    incremented under a row lock in the same transaction as the insert — see
    `ClientInvoiceService.generate_draft`.
    """

    __tablename__ = "client_invoices"
    __table_args__ = (
        UniqueConstraint("agency_id", "invoice_number", name="uq_client_invoice_agency_number"),
        Index("ix_client_invoice_agency_id", "agency_id"),
        Index("ix_client_invoice_brand_id", "brand_id"),
        Index("ix_client_invoice_status", "status"),
        CheckConstraint(
            "document_type IN ('draft_invoice', 'proforma')",
            name="ck_client_invoice_document_type_never_e_fatura",
        ),
        CheckConstraint(
            "total_cents = subtotal_cents - discount_cents + tax_cents",
            name="ck_client_invoice_total_matches_components",
        ),
        CheckConstraint("subtotal_cents >= 0", name="ck_client_invoice_subtotal_non_negative"),
        CheckConstraint("discount_cents >= 0", name="ck_client_invoice_discount_non_negative"),
        CheckConstraint("tax_cents >= 0", name="ck_client_invoice_tax_non_negative"),
        CheckConstraint("total_cents >= 0", name="ck_client_invoice_total_non_negative"),
        CheckConstraint(
            "amount_paid_cents >= 0", name="ck_client_invoice_amount_paid_non_negative"
        ),
        CheckConstraint("due_date >= issue_date", name="ck_client_invoice_due_after_issue"),
        CheckConstraint(
            "service_period_end IS NULL OR service_period_start IS NULL "
            "OR service_period_end >= service_period_start",
            name="ck_client_invoice_service_period_order",
        ),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    commercial_terms_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commercial_terms.id", ondelete="SET NULL"), nullable=True
    )
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    external_invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ClientInvoiceDocumentType.DRAFT_INVOICE.value
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    service_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount_paid_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ClientInvoiceStatus.DRAFT.value
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Snapshotted billing/tax identity — never a live FK-following read.
    billing_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tax_office: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Connector scaffolding (Phase 5) — columns exist, unpopulated in Phase 4.
    accounting_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ClientInvoice id={self.id} invoice_number={self.invoice_number} "
            f"status={self.status}>"
        )


class ClientInvoiceLine(BaseModel):
    """One billable line on a `ClientInvoice`. `source_type`/`source_id` is a
    polymorphic reference with no FK constraint (matches `ActivityLog`'s
    cross-entity ref pattern) — validated against `source_type` at the
    service layer, never the DB.

    Double-invoicing prevention: `TimeEntry.invoiced_at IS NOT NULL` gates
    re-selection at the service layer; the partial unique index below on
    `(source_id) WHERE source_type='time_entry' AND deleted_at IS NULL` is
    defense-in-depth. Voiding an invoice soft-deletes its time-entry-sourced
    lines (see `ClientInvoiceService.void`) precisely so that index frees up
    the underlying `TimeEntry` for a future invoice rather than colliding
    with the now-cancelled line forever.
    """

    __tablename__ = "client_invoice_lines"
    __table_args__ = (
        Index("ix_client_invoice_line_invoice_id", "invoice_id"),
        Index(
            "uq_client_invoice_line_time_entry_source",
            "source_id",
            unique=True,
            postgresql_where=text(
                "source_type = 'time_entry' AND source_id IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
        CheckConstraint("quantity > 0", name="ck_client_invoice_line_quantity_positive"),
        CheckConstraint(
            "unit_price_cents >= 0", name="ck_client_invoice_line_unit_price_non_negative"
        ),
        CheckConstraint("discount_cents >= 0", name="ck_client_invoice_line_discount_non_negative"),
        CheckConstraint("subtotal_cents >= 0", name="ck_client_invoice_line_subtotal_non_negative"),
        CheckConstraint("tax_cents >= 0", name="ck_client_invoice_line_tax_non_negative"),
        CheckConstraint("total_cents >= 0", name="ck_client_invoice_line_total_non_negative"),
        CheckConstraint(
            "total_cents = subtotal_cents - discount_cents + tax_cents",
            name="ck_client_invoice_line_total_matches_components",
        ),
        CheckConstraint(
            "billing_rate_snapshot_cents IS NULL OR billing_rate_snapshot_cents >= 0",
            name="ck_client_invoice_line_billing_rate_non_negative",
        ),
        CheckConstraint(
            "cost_rate_snapshot_cents IS NULL OR cost_rate_snapshot_cents >= 0",
            name="ck_client_invoice_line_cost_rate_non_negative",
        ),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_invoices.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # Internal-only — never rendered on the client-facing PDF/CSV.
    billing_rate_snapshot_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_rate_snapshot_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ClientInvoiceLine id={self.id} invoice_id={self.invoice_id} "
            f"source_type={self.source_type}>"
        )

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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
from app.models.enums import ConnectorStatus, ConnectorSyncStatus, PaymentSource


class AccountingConnector(BaseModel):
    """An agency's configured link to an external accounting provider
    (plan §3/§10). `manual` is the only provider ever actually dispatched
    to — `quickbooks`/`xero`/`logo`/`parasut`/`mikro` exist as `provider`
    values only, for future UI/schema readiness.

    `encrypted_credentials` is Fernet ciphertext (via `SecretEncryptionService`)
    and must NEVER be returned by any API response — enforced by the read
    schema simply never declaring the field, not by post-hoc filtering.
    `config` holds only non-secret settings (never a credential).
    """

    __tablename__ = "accounting_connectors"
    __table_args__ = (
        Index("ix_accounting_connector_agency_id", "agency_id"),
        Index(
            "uq_accounting_connector_one_per_provider",
            "agency_id",
            "provider",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ConnectorStatus.NOT_CONFIGURED.value
    )
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<AccountingConnector id={self.id} agency_id={self.agency_id} "
            f"provider={self.provider} status={self.status}>"
        )


class ConnectorSyncLog(BaseModel):
    """Imitates `BillingEvent`'s idempotency pattern (plan §3/§10): every
    dispatch through `AccountingConnectorService`, real or manual, writes
    exactly one row keyed by `idempotency_key`. A retried operation with the
    same key is a no-op READ of the prior row's result, never a duplicate
    dispatch to the underlying connector — this is what makes retries safe
    even once a real (webhook-driven) connector eventually exists.

    `request_payload`/`response_payload` are scrubbed of any
    credential-shaped key before being written (defense-in-depth, plan §12)
    — enforced by `AccountingConnectorService._redact`, not by this model.
    """

    __tablename__ = "connector_sync_logs"
    __table_args__ = (
        Index("ix_connector_sync_log_agency_id", "agency_id"),
        Index("ix_connector_sync_log_connector_id", "connector_id"),
        UniqueConstraint("idempotency_key", name="uq_connector_sync_log_idempotency_key"),
    )

    connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    related_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_invoices.id", ondelete="SET NULL"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ConnectorSyncStatus.PENDING.value
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ConnectorSyncLog id={self.id} connector_id={self.connector_id} "
            f"operation={self.operation} status={self.status}>"
        )


class Payment(BaseModel):
    """A payment recorded against a `ClientInvoice` (or an unallocated/
    advance payment when `invoice_id` is null) — plan §3. `external_payment_id`
    is unique where not null so a connector-sourced payment can never be
    ingested twice (defense against duplicate webhook delivery, even though
    v1 has zero real connectors calling `record_payment`/`fetch_payments`)."""

    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payment_agency_id", "agency_id"),
        Index("ix_payment_brand_id", "brand_id"),
        Index("ix_payment_invoice_id", "invoice_id"),
        Index(
            "uq_payment_external_payment_id",
            "external_payment_id",
            unique=True,
            postgresql_where=text("external_payment_id IS NOT NULL AND deleted_at IS NULL"),
        ),
        CheckConstraint("amount_cents > 0", name="ck_payment_amount_positive"),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_invoices.id", ondelete="SET NULL"), nullable=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    external_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PaymentSource.MANUAL.value
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} invoice_id={self.invoice_id} "
            f"amount_cents={self.amount_cents} source={self.source}>"
        )

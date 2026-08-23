"""add client invoicing

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-07-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOTE: `agency_settings.invoice_number_seq` already exists (added in
    # migration e7f8a9b0c1d2 ahead of schedule) — verified against the
    # current model/migration before writing this file, so no add_column
    # is needed here.

    # ── client_invoices ──────────────────────────────────────────────────────
    op.create_table(
        "client_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("commercial_terms_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("external_invoice_id", sa.String(255), nullable=True),
        sa.Column("document_type", sa.String(20), nullable=False, server_default="draft_invoice"),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("service_period_start", sa.Date(), nullable=True),
        sa.Column("service_period_end", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="TRY"),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tax_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("amount_paid_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("billing_contact_name", sa.String(255), nullable=True),
        sa.Column("billing_contact_email", sa.String(255), nullable=True),
        sa.Column("billing_address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tax_office", sa.String(255), nullable=True),
        sa.Column("tax_number", sa.String(50), nullable=True),
        sa.Column("accounting_provider", sa.String(30), nullable=True),
        sa.Column("provider_status", sa.String(30), nullable=True),
        sa.Column("provider_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["commercial_terms_id"], ["commercial_terms.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agency_id", "invoice_number", name="uq_client_invoice_agency_number"),
        sa.CheckConstraint(
            "document_type IN ('draft_invoice', 'proforma')",
            name="ck_client_invoice_document_type_never_e_fatura",
        ),
        sa.CheckConstraint(
            "total_cents = subtotal_cents - discount_cents + tax_cents",
            name="ck_client_invoice_total_matches_components",
        ),
        sa.CheckConstraint("subtotal_cents >= 0", name="ck_client_invoice_subtotal_non_negative"),
        sa.CheckConstraint("discount_cents >= 0", name="ck_client_invoice_discount_non_negative"),
        sa.CheckConstraint("tax_cents >= 0", name="ck_client_invoice_tax_non_negative"),
        sa.CheckConstraint("total_cents >= 0", name="ck_client_invoice_total_non_negative"),
        sa.CheckConstraint(
            "amount_paid_cents >= 0", name="ck_client_invoice_amount_paid_non_negative"
        ),
        sa.CheckConstraint("due_date >= issue_date", name="ck_client_invoice_due_after_issue"),
        sa.CheckConstraint(
            "service_period_end IS NULL OR service_period_start IS NULL "
            "OR service_period_end >= service_period_start",
            name="ck_client_invoice_service_period_order",
        ),
    )
    op.create_index("ix_client_invoice_agency_id", "client_invoices", ["agency_id"])
    op.create_index("ix_client_invoice_brand_id", "client_invoices", ["brand_id"])
    op.create_index("ix_client_invoice_status", "client_invoices", ["status"])

    # ── client_invoice_lines ─────────────────────────────────────────────────
    op.create_table(
        "client_invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("tax_rate_bps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("tax_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("billing_rate_snapshot_cents", sa.Integer(), nullable=True),
        sa.Column("cost_rate_snapshot_cents", sa.Integer(), nullable=True),
        sa.Column("service_period_start", sa.Date(), nullable=True),
        sa.Column("service_period_end", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["invoice_id"], ["client_invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("quantity > 0", name="ck_client_invoice_line_quantity_positive"),
        sa.CheckConstraint(
            "unit_price_cents >= 0", name="ck_client_invoice_line_unit_price_non_negative"
        ),
        sa.CheckConstraint(
            "discount_cents >= 0", name="ck_client_invoice_line_discount_non_negative"
        ),
        sa.CheckConstraint(
            "subtotal_cents >= 0", name="ck_client_invoice_line_subtotal_non_negative"
        ),
        sa.CheckConstraint("tax_cents >= 0", name="ck_client_invoice_line_tax_non_negative"),
        sa.CheckConstraint("total_cents >= 0", name="ck_client_invoice_line_total_non_negative"),
        sa.CheckConstraint(
            "total_cents = subtotal_cents - discount_cents + tax_cents",
            name="ck_client_invoice_line_total_matches_components",
        ),
        sa.CheckConstraint(
            "billing_rate_snapshot_cents IS NULL OR billing_rate_snapshot_cents >= 0",
            name="ck_client_invoice_line_billing_rate_non_negative",
        ),
        sa.CheckConstraint(
            "cost_rate_snapshot_cents IS NULL OR cost_rate_snapshot_cents >= 0",
            name="ck_client_invoice_line_cost_rate_non_negative",
        ),
    )
    op.create_index("ix_client_invoice_line_invoice_id", "client_invoice_lines", ["invoice_id"])
    op.create_index(
        "uq_client_invoice_line_time_entry_source",
        "client_invoice_lines",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text(
            "source_type = 'time_entry' AND source_id IS NOT NULL AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_client_invoice_line_time_entry_source", table_name="client_invoice_lines")
    op.drop_index("ix_client_invoice_line_invoice_id", table_name="client_invoice_lines")
    op.drop_table("client_invoice_lines")

    op.drop_index("ix_client_invoice_status", table_name="client_invoices")
    op.drop_index("ix_client_invoice_brand_id", table_name="client_invoices")
    op.drop_index("ix_client_invoice_agency_id", table_name="client_invoices")
    op.drop_table("client_invoices")

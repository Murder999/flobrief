"""add reporting tables

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-07-08 16:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6g7h8i9"
down_revision = "c3d4e5f6g7h8"
branch_labels = None
depends_on = None

UUID = sa.dialects.postgresql.UUID
JSONB = sa.dialects.postgresql.JSONB


def upgrade() -> None:
    # ── reports ───────────────────────────────────────────────────────────────
    op.create_table(
        "reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "agency_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agencies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("report_type", sa.String(30), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="'draft'"),
        sa.Column("title", sa.String(500), nullable=False),
    )
    op.create_index("ix_rep_agency_id", "reports", ["agency_id"])
    op.create_index("ix_rep_brand_id", "reports", ["brand_id"])
    op.create_index("ix_rep_status", "reports", ["status"])

    # ── report_snapshots ──────────────────────────────────────────────────────
    op.create_table(
        "report_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "report_id",
            UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metrics", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("narrative", JSONB, nullable=True),
    )
    op.create_index("ix_rsnap_report_id", "report_snapshots", ["report_id"])

    # ── report_share_tokens ───────────────────────────────────────────────────
    op.create_table(
        "report_share_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "report_id",
            UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "allow_pdf_download", sa.Boolean, nullable=False, server_default="true"
        ),
    )
    op.create_index(
        "ix_rst_token_hash", "report_share_tokens", ["token_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_rst_token_hash", "report_share_tokens")
    op.drop_table("report_share_tokens")
    op.drop_index("ix_rsnap_report_id", "report_snapshots")
    op.drop_table("report_snapshots")
    op.drop_index("ix_rep_status", "reports")
    op.drop_index("ix_rep_brand_id", "reports")
    op.drop_index("ix_rep_agency_id", "reports")
    op.drop_table("reports")

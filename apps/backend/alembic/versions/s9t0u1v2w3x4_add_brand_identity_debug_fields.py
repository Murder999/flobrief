"""add brand identity debug fields

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-07-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "brand_identity_documents",
        sa.Column("page_count", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "brand_identity_documents",
        sa.Column("extraction_method", sa.String(30), nullable=True),
    )
    op.add_column(
        "brand_identity_documents",
        sa.Column(
            "extraction_debug_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("brand_identity_documents", "extraction_debug_json")
    op.drop_column("brand_identity_documents", "extraction_method")
    op.drop_column("brand_identity_documents", "page_count")

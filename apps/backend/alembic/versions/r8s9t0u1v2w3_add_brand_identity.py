"""add brand identity DNA tables

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-07-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "r8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brand_identity_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("analysis_error", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bid_brand_id", "brand_identity_documents", ["brand_id"])

    op.create_table(
        "brand_identity_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brand_identity_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("primary_colors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("secondary_colors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("typography", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("logo_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("visual_style", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tone_of_voice", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("social_media_notes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("do_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("dont_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("key_takeaways", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence_score", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bip_brand_id", "brand_identity_profiles", ["brand_id"])

    op.create_table(
        "brand_identity_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brand_identity_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_by_name", sa.String(255), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("change_note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bir_profile_id", "brand_identity_revisions", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_bir_profile_id", table_name="brand_identity_revisions")
    op.drop_table("brand_identity_revisions")
    op.drop_index("ix_bip_brand_id", table_name="brand_identity_profiles")
    op.drop_table("brand_identity_profiles")
    op.drop_index("ix_bid_brand_id", table_name="brand_identity_documents")
    op.drop_table("brand_identity_documents")

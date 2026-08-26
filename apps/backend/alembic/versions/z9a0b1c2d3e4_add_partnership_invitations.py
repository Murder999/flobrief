"""Add secure agency-brand partnership invitations.

Revision ID: z9a0b1c2d3e4
Revises: w8x9y0z1a2b3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "z9a0b1c2d3e4"
down_revision: str | None = "w8x9y0z1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "partnership_invitations",
        sa.Column("direction", sa.String(length=40), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.CheckConstraint(
            "(direction = 'agency_invites_brand' AND agency_id IS NOT NULL AND brand_id IS NULL) "
            "OR (direction = 'brand_invites_agency' AND brand_id IS NOT NULL AND agency_id IS NULL)",
            name="ck_partnership_invitation_source",
        ),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_partnership_invitation_token_hash"),
    )
    op.create_index("ix_partnership_invitation_agency_id", "partnership_invitations", ["agency_id"])
    op.create_index("ix_partnership_invitation_brand_id", "partnership_invitations", ["brand_id"])
    op.create_index("ix_partnership_invitation_email", "partnership_invitations", ["email"])
    op.create_index(
        "ix_partnership_invitation_expires_at", "partnership_invitations", ["expires_at"]
    )
    op.create_index(
        "ix_partnership_invitation_invited_by", "partnership_invitations", ["invited_by"]
    )


def downgrade() -> None:
    op.drop_table("partnership_invitations")

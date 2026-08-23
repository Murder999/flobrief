"""add invitations table

Revision ID: c1e2f3a4b5d6
Revises: b8f2a9c3d1e5
Create Date: 2026-07-08 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision: str = "c1e2f3a4b5d6"
down_revision: str = "b8f2a9c3d1e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agency_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("agencies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("invitation_type", sa.String(20), nullable=False, server_default="agency"),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column(
            "invited_by",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_invitation_token_hash", "invitations", ["token_hash"])
    op.create_index("ix_invitation_agency_id", "invitations", ["agency_id"])
    op.create_index("ix_invitation_brand_id", "invitations", ["brand_id"])
    op.create_index("ix_invitation_email", "invitations", ["email"])
    op.create_index("ix_invitation_invited_by", "invitations", ["invited_by"])
    op.create_index("ix_invitation_expires_at", "invitations", ["expires_at"])
    op.create_index("ix_invitation_agency_email", "invitations", ["agency_id", "email"])


def downgrade() -> None:
    op.drop_table("invitations")

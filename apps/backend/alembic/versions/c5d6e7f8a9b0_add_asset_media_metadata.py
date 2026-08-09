"""add asset media metadata (width_px/height_px)

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-07-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("width_px", sa.Integer(), nullable=True))
    op.add_column("assets", sa.Column("height_px", sa.Integer(), nullable=True))
    op.add_column("asset_versions", sa.Column("width_px", sa.Integer(), nullable=True))
    op.add_column("asset_versions", sa.Column("height_px", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("asset_versions", "height_px")
    op.drop_column("asset_versions", "width_px")
    op.drop_column("assets", "height_px")
    op.drop_column("assets", "width_px")

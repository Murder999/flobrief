"""rename time_entry rate snapshot

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-07-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a9b0c1d2e3f4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `rate_snapshot_cents` has never been written by any Part 1 code path —
    # safe to rename in place (zero data risk) rather than add-and-migrate.
    op.alter_column(
        "time_entries", "rate_snapshot_cents", new_column_name="billing_rate_snapshot_cents"
    )
    op.add_column(
        "time_entries", sa.Column("cost_rate_snapshot_cents", sa.Integer(), nullable=True)
    )
    op.add_column(
        "time_entries", sa.Column("rate_currency_snapshot", sa.String(3), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("time_entries", "rate_currency_snapshot")
    op.drop_column("time_entries", "cost_rate_snapshot_cents")
    op.alter_column(
        "time_entries", "billing_rate_snapshot_cents", new_column_name="rate_snapshot_cents"
    )

"""fix deliverables.submitted_at/approved_at to be timezone-aware

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-16

deliverables.submitted_at/approved_at were created as TIMESTAMP WITHOUT TIME
ZONE, but application code always writes timezone-aware datetime.now(UTC)
into them. asyncpg rejects that mismatch at write time (confirmed via a live
DB error during submit_deliverable), so this had never actually worked
against a real Postgres database. Existing naive values (if any slipped in
via a path that didn't hit this bug) are assumed to already be UTC.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "deliverables",
        "submitted_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="submitted_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "deliverables",
        "approved_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="approved_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "deliverables",
        "submitted_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="submitted_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "deliverables",
        "approved_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="approved_at AT TIME ZONE 'UTC'",
    )

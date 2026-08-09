"""unique_notification_delivery_idempotency_key

Part 6B-1 closing — domain-level WhatsApp delivery idempotency.

`notification_deliveries.idempotency_key` was only ever backed by a plain
(non-unique) btree index (`ix_ndel_idempotency_key`, added in
f3g4h5i6j7k8_whatsapp_template_registry.py). The dispatcher's own
check-then-insert was therefore a race: two concurrent callers could both
pass the "does this key already exist?" SELECT before either committed its
INSERT, producing two delivery rows (and, worse, two real provider sends)
for what should be a single idempotent delivery.

This migration:
1. Defensively collapses any pre-existing duplicate (non-null)
   idempotency_key rows down to one (the earliest by created_at/id),
   deleting the rest — a real duplicate here would violate the unique
   index we're about to add.
2. Drops the old plain index and replaces it with a unique index of the
   same name. NULLs remain unrestricted (every non-WhatsApp delivery row
   has idempotency_key=NULL, and Postgres unique indexes never treat NULLs
   as equal to each other), so this only constrains WhatsApp rows that
   actually set the key.

Revision ID: p1q2r3s4t5u6
Revises: n8o9p0q1r2s3
Create Date: 2026-07-28 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, None] = "n8o9p0q1r2s3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep the earliest row per duplicate idempotency_key, delete the rest.
    op.execute(
        """
        DELETE FROM notification_deliveries nd
        USING (
            SELECT id,
                   idempotency_key,
                   ROW_NUMBER() OVER (
                       PARTITION BY idempotency_key
                       ORDER BY created_at ASC, id ASC
                   ) AS rn
            FROM notification_deliveries
            WHERE idempotency_key IS NOT NULL
        ) dupes
        WHERE nd.id = dupes.id
          AND dupes.rn > 1
        """
    )

    op.drop_index("ix_ndel_idempotency_key", table_name="notification_deliveries")
    op.create_index(
        "ix_ndel_idempotency_key",
        "notification_deliveries",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_ndel_idempotency_key", table_name="notification_deliveries")
    op.create_index(
        "ix_ndel_idempotency_key",
        "notification_deliveries",
        ["idempotency_key"],
        unique=False,
    )

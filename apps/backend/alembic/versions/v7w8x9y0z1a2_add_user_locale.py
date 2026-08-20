"""Add an allowlisted user interface locale.

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
Create Date: 2026-08-21 00:00:00.000000
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "v7w8x9y0z1a2"
down_revision: Union[str, None] = "u6v7w8x9y0z1"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("locale", sa.String(length=5), nullable=True))
    op.create_check_constraint(
        "ck_users_locale_supported",
        "users",
        "locale IS NULL OR locale IN ('en', 'tr')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_locale_supported", "users", type_="check")
    op.drop_column("users", "locale")

"""add capacity tables

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-07-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── work_schedules ───────────────────────────────────────────────────────
    op.create_table(
        "work_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Europe/Istanbul"),
        sa.Column("effective_from", sa.Date(), nullable=True),
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
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_schedule_agency_id", "work_schedules", ["agency_id"])
    op.create_index("ix_work_schedule_user_id", "work_schedules", ["user_id"])
    op.create_index(
        "uq_work_schedule_one_active_per_user",
        "work_schedules",
        ["agency_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ── work_schedule_days ───────────────────────────────────────────────────
    op.create_table(
        "work_schedule_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("is_working_day", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("capacity_minutes", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["work_schedule_id"], ["work_schedules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_schedule_id", "weekday", name="uq_work_schedule_day_weekday"),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6", name="ck_work_schedule_day_weekday_range"
        ),
        sa.CheckConstraint(
            "capacity_minutes >= 0", name="ck_work_schedule_day_capacity_non_negative"
        ),
    )
    op.create_index(
        "ix_work_schedule_day_work_schedule_id", "work_schedule_days", ["work_schedule_id"]
    )

    # ── capacity_exceptions ──────────────────────────────────────────────────
    op.create_table(
        "capacity_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("capacity_minutes", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("exception_type", sa.String(20), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "capacity_minutes >= 0", name="ck_capacity_exception_capacity_non_negative"
        ),
    )
    op.create_index("ix_capacity_exception_agency_id", "capacity_exceptions", ["agency_id"])
    op.create_index("ix_capacity_exception_user_id", "capacity_exceptions", ["user_id"])
    op.create_index(
        "uq_capacity_exception_user_date",
        "capacity_exceptions",
        ["user_id", "date"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ── time_off ─────────────────────────────────────────────────────────────
    op.create_table(
        "time_off",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="requested"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("end_at >= start_at", name="ck_time_off_end_after_start"),
    )
    op.create_index("ix_time_off_agency_id", "time_off", ["agency_id"])
    op.create_index("ix_time_off_user_id", "time_off", ["user_id"])
    op.create_index("ix_time_off_start_at", "time_off", ["start_at"])

    # ── work_allocations ─────────────────────────────────────────────────────
    op.create_table(
        "work_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deliverable_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(30), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("allocated_minutes", sa.Integer(), nullable=False),
        sa.Column("allocation_source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["brief_id"], ["briefs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["brief_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deliverable_id"], ["deliverables.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("end_date >= start_date", name="ck_work_allocation_end_after_start"),
        sa.CheckConstraint("allocated_minutes > 0", name="ck_work_allocation_minutes_positive"),
    )
    op.create_index("ix_work_allocation_agency_id", "work_allocations", ["agency_id"])
    op.create_index("ix_work_allocation_user_id", "work_allocations", ["user_id"])
    op.create_index("ix_work_allocation_brief_id", "work_allocations", ["brief_id"])
    op.create_index("ix_work_allocation_brand_id", "work_allocations", ["brand_id"])
    op.create_index("ix_work_allocation_start_date", "work_allocations", ["start_date"])

    # ── agency_settings ──────────────────────────────────────────────────────
    op.create_table(
        "agency_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "capacity_available_threshold_pct",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
        sa.Column(
            "capacity_balanced_threshold_pct",
            sa.Integer(),
            nullable=False,
            server_default="85",
        ),
        sa.Column(
            "capacity_near_threshold_pct", sa.Integer(), nullable=False, server_default="100"
        ),
        sa.Column("default_currency", sa.String(3), nullable=False, server_default="TRY"),
        sa.Column("default_payment_terms_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("invoice_number_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "retainer_default_rollover",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agency_id", name="uq_agency_settings_agency_id"),
    )


def downgrade() -> None:
    op.drop_table("agency_settings")

    op.drop_index("ix_work_allocation_start_date", table_name="work_allocations")
    op.drop_index("ix_work_allocation_brand_id", table_name="work_allocations")
    op.drop_index("ix_work_allocation_brief_id", table_name="work_allocations")
    op.drop_index("ix_work_allocation_user_id", table_name="work_allocations")
    op.drop_index("ix_work_allocation_agency_id", table_name="work_allocations")
    op.drop_table("work_allocations")

    op.drop_index("ix_time_off_start_at", table_name="time_off")
    op.drop_index("ix_time_off_user_id", table_name="time_off")
    op.drop_index("ix_time_off_agency_id", table_name="time_off")
    op.drop_table("time_off")

    op.drop_index("uq_capacity_exception_user_date", table_name="capacity_exceptions")
    op.drop_index("ix_capacity_exception_user_id", table_name="capacity_exceptions")
    op.drop_index("ix_capacity_exception_agency_id", table_name="capacity_exceptions")
    op.drop_table("capacity_exceptions")

    op.drop_index("ix_work_schedule_day_work_schedule_id", table_name="work_schedule_days")
    op.drop_table("work_schedule_days")

    op.drop_index("uq_work_schedule_one_active_per_user", table_name="work_schedules")
    op.drop_index("ix_work_schedule_user_id", table_name="work_schedules")
    op.drop_index("ix_work_schedule_agency_id", table_name="work_schedules")
    op.drop_table("work_schedules")

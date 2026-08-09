from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class Report(BaseModel):
    """Aggregated report for an agency (or a specific brand) over a time period."""

    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_rep_agency_id", "agency_id"),
        Index("ix_rep_brand_id", "brand_id"),
        Index("ix_rep_status", "status"),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    title: Mapped[str] = mapped_column(String(500), nullable=False)


class ReportSnapshot(BaseModel):
    """Immutable snapshot of computed metrics at generation time.

    Preserved independently of source data changes — snapshots are forensic.
    """

    __tablename__ = "report_snapshots"
    __table_args__ = (Index("ix_rsnap_report_id", "report_id"),)

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    narrative: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ReportShareToken(BaseModel):
    """Secure share token for public report access. Raw token never stored in DB."""

    __tablename__ = "report_share_tokens"
    __table_args__ = (Index("ix_rst_token_hash", "token_hash", unique=True),)

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    allow_pdf_download: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

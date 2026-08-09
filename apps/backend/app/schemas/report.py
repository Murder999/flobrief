from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    report_type: str
    period_start: date
    period_end: date
    title: str = Field(min_length=1, max_length=500)
    brand_id: uuid.UUID | None = None


class ReportRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None
    created_by_id: uuid.UUID | None
    report_type: str
    period_start: date
    period_end: date
    status: str
    title: str
    created_at: datetime
    updated_at: datetime


class ReportWithSnapshot(ReportRead):
    snapshot: ReportSnapshotRead | None = None
    active_share_tokens: list[ReportShareTokenRead] = Field(default_factory=list)


class ReportSnapshotRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    report_id: uuid.UUID
    metrics: dict
    narrative: dict | None
    created_at: datetime


class ReportShareTokenCreate(BaseModel):
    expires_in_days: int = Field(default=30, ge=1, le=365)
    allow_pdf_download: bool = True


class ReportShareTokenRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    report_id: uuid.UUID
    expires_at: datetime
    revoked_at: datetime | None
    allow_pdf_download: bool
    created_at: datetime


class ReportShareTokenCreated(ReportShareTokenRead):
    """Returned once on creation — contains raw token. Never stored."""

    token: str


class PublicReportView(BaseModel):
    """Public-facing report view. No internal IDs or tenant data."""

    report_type: str
    period_start: date
    period_end: date
    title: str
    metrics: dict
    narrative: dict | None
    generated_at: datetime
    allow_pdf_download: bool


class ReportListResponse(BaseModel):
    items: list[ReportRead]
    total: int
    limit: int
    offset: int

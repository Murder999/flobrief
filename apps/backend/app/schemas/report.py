from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import ReportType


class ReportCreate(BaseModel):
    report_type: ReportType
    period_start: date
    period_end: date
    title: str = Field(min_length=1, max_length=500)
    brand_id: uuid.UUID | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Report title cannot be blank")
        return title

    @model_validator(mode="after")
    def validate_period(self) -> ReportCreate:
        if self.period_start > self.period_end:
            raise ValueError("period_start must be on or before period_end")
        return self


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


class BrandReportSnapshotRead(BaseModel):
    """Brand-facing snapshot without agency-internal identifiers."""

    model_config = {"from_attributes": True}

    metrics: dict
    narrative: dict | None
    created_at: datetime


class BrandReportWithSnapshot(BaseModel):
    """Read-only report view scoped by the authenticated Brand membership."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    report_type: str
    period_start: date
    period_end: date
    status: str
    title: str
    created_at: datetime
    snapshot: BrandReportSnapshotRead | None = None


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

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.time_entry import TimeEntryRead


class CategoryBreakdown(BaseModel):
    category: str
    hours: float
    entry_count: int


class BriefTimeSummary(BaseModel):
    """Estimate/actual/remaining/variance for one brief — always computed on
    read from real TimeEntry rows. Never stored, so it can never go stale."""

    brief_id: uuid.UUID
    estimated_hours: float | None
    estimated_hours_by_category: dict[str, float] | None
    actual_hours: float
    remaining_hours: float | None
    variance_hours: float | None
    is_over_estimate: bool
    entry_count: int
    category_breakdown: list[CategoryBreakdown]


class BrandTimeSummary(BaseModel):
    brand_id: uuid.UUID
    total_hours: float
    billable_hours: float
    non_billable_hours: float
    brief_count: int
    entry_count: int
    category_breakdown: list[CategoryBreakdown]


class UserTimeSummary(BaseModel):
    user_id: uuid.UUID
    user_name: str
    total_hours: float
    billable_hours: float
    entry_count: int


class WeeklyTimesheetResponse(BaseModel):
    user_id: uuid.UUID
    start_date: date
    end_date: date
    entries: list[TimeEntryRead]
    total_hours: float
    billable_hours: float
    by_day: dict[str, float]


class TeamTimeReportResponse(BaseModel):
    start_date: date
    end_date: date
    users: list[UserTimeSummary]
    total_hours: float
    billable_hours: float


class MissingTimesheetEntry(BaseModel):
    user_id: uuid.UUID
    user_name: str
    missing_date: date


class MissingTimesheetResponse(BaseModel):
    start_date: date
    end_date: date
    missing: list[MissingTimesheetEntry]


class TimeReportRangeQuery(BaseModel):
    """Shared date-range validation for report endpoints."""

    start_date: date
    end_date: date

    def validate_range(self) -> None:
        if self.end_date < self.start_date:
            from app.core.exceptions import ValidationError

            raise ValidationError("Bitiş tarihi başlangıçtan önce olamaz")

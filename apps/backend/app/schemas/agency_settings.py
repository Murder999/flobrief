from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class AgencySettingsUpdate(BaseModel):
    capacity_available_threshold_pct: int | None = Field(None, ge=0, le=100)
    capacity_balanced_threshold_pct: int | None = Field(None, ge=0, le=100)
    capacity_near_threshold_pct: int | None = Field(None, ge=0, le=100)
    default_currency: str | None = Field(None, min_length=3, max_length=3)
    default_payment_terms_days: int | None = Field(None, ge=0)
    retainer_default_rollover: bool | None = None

    @model_validator(mode="after")
    def validate_threshold_ordering(self) -> AgencySettingsUpdate:
        available = self.capacity_available_threshold_pct
        balanced = self.capacity_balanced_threshold_pct
        near = self.capacity_near_threshold_pct
        values = [v for v in (available, balanced, near) if v is not None]
        if len(values) == 3 and not (available <= balanced <= near):  # type: ignore[operator]
            raise ValueError("Eşikler sıralı olmalı: müsait <= dengeli <= kapasiteye yakın")
        return self


class AgencySettingsRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    capacity_available_threshold_pct: int
    capacity_balanced_threshold_pct: int
    capacity_near_threshold_pct: int
    default_currency: str
    default_payment_terms_days: int
    invoice_number_seq: int
    retainer_default_rollover: bool
    updated_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

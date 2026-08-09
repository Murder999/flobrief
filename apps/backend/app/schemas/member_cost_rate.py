from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import AgencyMemberRole

_VALID_ROLES = {r.value for r in AgencyMemberRole}

# Kept in sync with app.schemas.commercial_terms — same curated ISO 4217
# allowlist, duplicated rather than imported to keep the two finance schema
# modules independently reviewable (cost rates are the more sensitive one).
_VALID_CURRENCIES = {
    "TRY",
    "USD",
    "EUR",
    "GBP",
    "CHF",
    "JPY",
    "CAD",
    "AUD",
    "SEK",
    "NOK",
    "DKK",
    "PLN",
    "CZK",
    "HUF",
    "RON",
    "BGN",
    "RUB",
    "AED",
    "SAR",
    "QAR",
    "KWD",
    "ILS",
    "CNY",
    "HKD",
    "SGD",
    "INR",
    "ZAR",
    "BRL",
    "MXN",
    "AZN",
}


def _validate_currency(v: str) -> str:
    v = v.upper().strip()
    if v not in _VALID_CURRENCIES:
        raise ValueError(f"Geçersiz para birimi kodu (ISO 4217): {v}")
    return v


class MemberCostRateCreate(BaseModel):
    """Exactly one of `user_id`/`role` must be set — a per-user override or a
    per-role fallback rate, never both, never neither (mirrors the DB check
    constraint as defense-in-depth). This schema and `MemberCostRateRead`
    must never be embedded in any team-member listing or response reachable
    by a role lacking `COST_RATE_VIEW` — cost rates are Owner-only data."""

    user_id: uuid.UUID | None = None
    role: str | None = None
    currency: str = Field(..., min_length=3, max_length=3)
    hourly_cost_cents: int = Field(..., gt=0)
    valid_from: date
    valid_until: date | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_ROLES:
            raise ValueError(f"Geçersiz rol: {v}")
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return _validate_currency(v)

    @model_validator(mode="after")
    def validate_exactly_one_target(self) -> MemberCostRateCreate:
        if (self.user_id is None) == (self.role is None):
            raise ValueError(
                "Tam olarak biri belirtilmeli: kullanıcı veya rol (ikisi birden değil)"
            )
        return self

    @model_validator(mode="after")
    def validate_valid_range(self) -> MemberCostRateCreate:
        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise ValueError("Bitiş tarihi başlangıç tarihinden önce olamaz")
        return self


class MemberCostRateUpdate(BaseModel):
    currency: str | None = Field(None, min_length=3, max_length=3)
    hourly_cost_cents: int | None = Field(None, gt=0)
    valid_until: date | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_currency(v)


class MemberCostRateRead(BaseModel):
    """Owner/Finance-only response model. Callers must gate every path that
    returns this schema behind `COST_RATE_VIEW` at the API layer AND an
    explicit role check at the service layer — see
    `MemberCostRateService._require_finance_visibility`."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    user_id: uuid.UUID | None
    role: str | None
    currency: str
    hourly_cost_cents: int
    valid_from: date
    valid_until: date | None
    active: bool
    created_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

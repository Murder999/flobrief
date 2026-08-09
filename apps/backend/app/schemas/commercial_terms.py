from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.enums import CommercialTermsBillingModel

_VALID_BILLING_MODELS = {m.value for m in CommercialTermsBillingModel}

# ISO 4217 three-letter codes for currencies realistically used by Flobrief
# agencies/brands. Not the full ISO 4217 table — a deliberately curated
# allowlist so a typo'd currency code fails fast at the schema boundary
# rather than silently reaching invoicing math.
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


class CommercialTermsCreate(BaseModel):
    """Explicit field allowlist — mass-assignment guard per plan §12. Never
    accepts `agency_id`/`active`/`created_by_id`/`updated_by_id` from the
    client; those are always set by the service from the authenticated
    workspace context."""

    brand_id: uuid.UUID
    billing_model: str
    currency: str = Field(..., min_length=3, max_length=3)
    hourly_rate_cents: int | None = Field(None, ge=0)
    fixed_fee_cents: int | None = Field(None, ge=0)
    retainer_amount_cents: int | None = Field(None, ge=0)
    retainer_included_minutes: int | None = Field(None, ge=0)
    overage_rate_cents: int | None = Field(None, ge=0)
    per_item_rate_cents: int | None = Field(None, ge=0)
    payment_terms_days: int = Field(30, ge=0)
    tax_rate_bps: int = Field(0, ge=0, le=10000)
    discount_rate_bps: int | None = Field(None, ge=0, le=10000)
    billing_contact_name: str | None = None
    billing_contact_email: EmailStr | None = None
    billing_address: dict | None = None
    tax_office: str | None = None
    tax_number: str | None = None
    valid_from: date
    valid_until: date | None = None

    @field_validator("billing_model")
    @classmethod
    def validate_billing_model(cls, v: str) -> str:
        if v not in _VALID_BILLING_MODELS:
            raise ValueError(f"Geçersiz faturalama modeli: {v}")
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return _validate_currency(v)

    @model_validator(mode="after")
    def validate_valid_range(self) -> CommercialTermsCreate:
        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise ValueError("Bitiş tarihi başlangıç tarihinden önce olamaz")
        return self


class CommercialTermsUpdate(BaseModel):
    billing_model: str | None = None
    currency: str | None = Field(None, min_length=3, max_length=3)
    hourly_rate_cents: int | None = Field(None, ge=0)
    fixed_fee_cents: int | None = Field(None, ge=0)
    retainer_amount_cents: int | None = Field(None, ge=0)
    retainer_included_minutes: int | None = Field(None, ge=0)
    overage_rate_cents: int | None = Field(None, ge=0)
    per_item_rate_cents: int | None = Field(None, ge=0)
    payment_terms_days: int | None = Field(None, ge=0)
    tax_rate_bps: int | None = Field(None, ge=0, le=10000)
    discount_rate_bps: int | None = Field(None, ge=0, le=10000)
    billing_contact_name: str | None = None
    billing_contact_email: EmailStr | None = None
    billing_address: dict | None = None
    tax_office: str | None = None
    tax_number: str | None = None
    valid_until: date | None = None

    @field_validator("billing_model")
    @classmethod
    def validate_billing_model(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_BILLING_MODELS:
            raise ValueError(f"Geçersiz faturalama modeli: {v}")
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_currency(v)


class CommercialTermsRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID
    billing_model: str
    currency: str
    hourly_rate_cents: int | None
    fixed_fee_cents: int | None
    retainer_amount_cents: int | None
    retainer_included_minutes: int | None
    overage_rate_cents: int | None
    per_item_rate_cents: int | None
    payment_terms_days: int
    tax_rate_bps: int
    discount_rate_bps: int | None
    billing_contact_name: str | None
    billing_contact_email: str | None
    billing_address: dict | None
    tax_office: str | None
    tax_number: str | None
    valid_from: date
    valid_until: date | None
    active: bool
    created_by_id: uuid.UUID | None
    updated_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

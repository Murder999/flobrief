from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import PaymentMethod

_VALID_PAYMENT_METHODS = {m.value for m in PaymentMethod}


class PaymentCreate(BaseModel):
    """Explicit field allowlist (plan §12). `allow_overpayment` must be
    explicitly passed `True` by the caller to permit a payment that would
    exceed an invoice's remaining balance — the default always rejects."""

    brand_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    amount_cents: int = Field(..., gt=0)
    currency: str = Field(default="TRY", min_length=3, max_length=3)
    payment_method: str
    paid_at: datetime
    external_payment_id: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, max_length=4000)
    allow_overpayment: bool = False

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: str) -> str:
        if v not in _VALID_PAYMENT_METHODS:
            raise ValueError(f"Geçersiz ödeme yöntemi: {v}")
        return v


class PaymentRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID
    invoice_id: uuid.UUID | None
    amount_cents: int
    currency: str
    payment_method: str
    paid_at: datetime
    external_payment_id: str | None
    source: str
    notes: str | None
    recorded_by_id: uuid.UUID | None
    created_at: datetime

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class PlanRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    monthly_price_cents: int
    yearly_price_cents: int
    currency: str
    max_brands: int | None
    max_users: int | None
    max_brand_users: int | None
    max_brief_templates: int | None
    max_storage_gb: int | None
    max_pending_agency_invites: int | None
    max_pending_brand_invites: int | None
    white_label_enabled: bool
    advanced_reporting_enabled: bool
    pdf_export_enabled: bool
    public_report_link_enabled: bool
    whatsapp_infrastructure_enabled: bool
    is_active: bool

    model_config = {"from_attributes": True}


class SubscriptionRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    plan_id: uuid.UUID
    plan: PlanRead
    status: str
    billing_provider: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool

    model_config = {"from_attributes": True}


class CheckoutRequest(BaseModel):
    plan_id: uuid.UUID
    yearly: bool = False


class CheckoutResponse(BaseModel):
    payment_page_url: str | None
    token: str | None
    plan_code: str
    amount_cents: int
    currency: str
    provider: str
    sandbox: bool = False


class ChangePlanRequest(BaseModel):
    plan_id: uuid.UUID


class InvoiceRead(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID
    provider_invoice_id: str | None
    amount_cents: int
    currency: str
    status: str
    period_start: datetime | None
    period_end: datetime | None
    hosted_invoice_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UsageSummary(BaseModel):
    plan_code: str | None
    plan_name: str | None
    brands: dict
    users: dict
    brief_templates: dict
    storage_gb: dict
    features: dict


class EntitlementCheckRequest(BaseModel):
    feature: str


class EntitlementCheckResponse(BaseModel):
    feature: str
    allowed: bool
    reason: str | None = None

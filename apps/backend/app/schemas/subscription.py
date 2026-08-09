import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import BillingProvider, SubscriptionStatus


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    plan_id: uuid.UUID
    status: SubscriptionStatus
    billing_provider: BillingProvider
    provider_customer_id: str | None
    provider_subscription_id: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: datetime

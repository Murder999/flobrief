import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import PlanCode


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: PlanCode
    name: str
    description: str | None
    monthly_price_cents: int
    yearly_price_cents: int
    currency: str
    max_brands: int | None
    max_users: int | None
    max_brief_templates: int | None
    max_storage_gb: int | None
    white_label_enabled: bool
    advanced_reporting_enabled: bool
    pdf_export_enabled: bool
    public_report_link_enabled: bool
    whatsapp_infrastructure_enabled: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

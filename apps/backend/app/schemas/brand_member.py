import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import BrandMemberRole, BrandMemberStatus


class BrandMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    user_id: uuid.UUID
    role: BrandMemberRole
    status: BrandMemberStatus
    joined_at: datetime | None
    created_at: datetime
    updated_at: datetime

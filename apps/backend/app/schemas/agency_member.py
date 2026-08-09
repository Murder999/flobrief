import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AgencyMemberRole, AgencyMemberStatus


class AgencyMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID
    user_id: uuid.UUID
    role: AgencyMemberRole
    status: AgencyMemberStatus
    joined_at: datetime | None
    created_at: datetime
    updated_at: datetime

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ActivityLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    meta: dict | None
    ip_address: str | None
    created_at: datetime


class ActivityLogListResponse(BaseModel):
    items: list[ActivityLogRead]
    total: int
    limit: int
    offset: int

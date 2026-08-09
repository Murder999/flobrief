import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PlatformAuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    admin_user_id: uuid.UUID
    action: str
    target_type: str | None
    target_id: uuid.UUID | None
    target_tenant_type: str | None
    target_tenant_id: uuid.UUID | None
    ip_address: str | None
    user_agent: str | None
    meta: dict[str, Any] | None
    created_at: datetime

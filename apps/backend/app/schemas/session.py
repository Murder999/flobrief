"""Schemas for the authenticated user's own active-sessions view."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class SessionRead(BaseModel):
    id: uuid.UUID
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}

from __future__ import annotations

from pydantic import BaseModel


class PermissionResponse(BaseModel):
    user_type: str
    agency_id: str | None
    role: str | None
    permissions: list[str]

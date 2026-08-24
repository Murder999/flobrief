from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DemoPublicStatus(BaseModel):
    enabled: bool
    available: bool
    unavailable_reason: str | None = None
    duration_hours: int
    captcha_required: bool
    captcha_site_key: str | None = None
    active_sandboxes: int
    capacity: int


class DemoStartRequest(BaseModel):
    turnstile_token: str | None = Field(default=None, max_length=4096)


class DemoStartResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    agency_id: uuid.UUID
    expires_at: datetime


class DemoSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    duration_hours: int
    max_active_sandboxes: int
    max_creations_per_ip_per_day: int
    captcha_required: bool
    captcha_configured: bool
    active_sandboxes: int
    total_created: int
    expired_or_terminated: int


class DemoSettingsUpdate(BaseModel):
    enabled: bool | None = None
    duration_hours: int | None = Field(default=None, ge=1, le=72)
    max_active_sandboxes: int | None = Field(default=None, ge=1, le=500)
    max_creations_per_ip_per_day: int | None = Field(default=None, ge=1, le=20)
    captcha_required: bool | None = None


class DemoSandboxRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID
    owner_user_id: uuid.UUID
    agency_name: str
    status: str
    expires_at: datetime
    terminated_at: datetime | None
    termination_reason: str | None
    created_at: datetime


class DemoSessionStatus(BaseModel):
    is_demo: bool
    active_portal: str | None = None
    expires_at: str | None = None


class DemoPortalSwitchRequest(BaseModel):
    portal: Literal["agency", "brand"]


class DemoPortalSwitchResponse(BaseModel):
    portal: str
    redirect_to: str
    expires_at: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int

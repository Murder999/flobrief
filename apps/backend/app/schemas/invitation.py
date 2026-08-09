from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import AgencyMemberRole, BrandMemberRole


class AgencyInviteRequest(BaseModel):
    email: EmailStr
    role: str
    message: str | None = Field(None, max_length=500)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("role")
    @classmethod
    def validate_agency_role(cls, v: str) -> str:
        valid = {r.value for r in AgencyMemberRole}
        if v not in valid:
            msg = f"Invalid agency role. Valid: {sorted(valid)}"
            raise ValueError(msg)
        return v


class BrandInviteRequest(BaseModel):
    email: EmailStr
    role: str
    message: str | None = Field(None, max_length=500)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("role")
    @classmethod
    def validate_brand_role(cls, v: str) -> str:
        valid = {r.value for r in BrandMemberRole}
        if v not in valid:
            msg = f"Invalid brand role. Valid: {sorted(valid)}"
            raise ValueError(msg)
        return v


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None
    invitation_type: str
    email: str
    role: str
    invited_by: uuid.UUID
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    rejected_at: datetime | None
    resent_count: int
    created_at: datetime
    is_pending: bool


class InvitationPreview(BaseModel):
    """Public (no-auth) view of an invitation for the accept flow."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID
    agency_name: str
    brand_id: uuid.UUID | None
    brand_name: str | None
    invitation_type: str
    email: str
    role: str
    expires_at: datetime
    is_pending: bool

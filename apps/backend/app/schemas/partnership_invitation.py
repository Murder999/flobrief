from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class PartnershipInviteCreate(BaseModel):
    email: EmailStr
    message: str | None = Field(default=None, max_length=500)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PartnershipInviteAccept(BaseModel):
    target_workspace_id: uuid.UUID | None = None
    new_workspace_name: str | None = Field(default=None, min_length=2, max_length=120)

    @model_validator(mode="after")
    def exactly_one_target(self) -> PartnershipInviteAccept:
        if (self.target_workspace_id is None) == (self.new_workspace_name is None):
            raise ValueError("Mevcut çalışma alanı veya yeni çalışma alanı adı seçilmelidir")
        if self.new_workspace_name is not None:
            self.new_workspace_name = self.new_workspace_name.strip()
        return self


class PartnershipInvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    direction: Literal["agency_invites_brand", "brand_invites_agency"]
    agency_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    email: str
    invited_by: uuid.UUID
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    is_pending: bool


class PartnershipInvitationPreview(BaseModel):
    direction: Literal["agency_invites_brand", "brand_invites_agency"]
    source_name: str
    email: str
    expires_at: datetime
    state: Literal["pending", "accepted", "expired", "revoked"]
    required_workspace_type: Literal["agency", "brand"]


class PartnershipAcceptResponse(BaseModel):
    agency_id: uuid.UUID
    brand_id: uuid.UUID
    redirect_to: Literal["/dashboard", "/brand/dashboard"]

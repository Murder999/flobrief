import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import AgencyMemberRole, AgencyStatus


class AgencyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str | None = Field(None, min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, v: str | None) -> str | None:
        return v.lower().strip() if v else None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class AgencyUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        return v.strip() if v else None


class AgencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: AgencyStatus
    owner_user_id: uuid.UUID | None
    plan_id: uuid.UUID | None
    logo_url: str | None = None
    created_at: datetime
    updated_at: datetime


class AgencyWithRole(AgencyRead):
    """Agency + the current user's membership role."""

    member_role: str
    member_status: str


class AgencyMemberWithUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID
    user_id: uuid.UUID
    role: AgencyMemberRole
    status: str
    joined_at: datetime | None
    created_at: datetime
    user_email: str | None = None
    user_full_name: str | None = None


class AgencyMemberRoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid = {r.value for r in AgencyMemberRole} - {"owner"}
        if v not in valid:
            msg = f"Invalid role. Valid (cannot set owner via API): {sorted(valid)}"
            raise ValueError(msg)
        return v

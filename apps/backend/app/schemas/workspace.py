from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class WorkspaceAgency(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: str
    logo_url: str | None = None
    member_role: str
    member_status: str


class WorkspaceBrand(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID | None
    name: str
    slug: str
    status: str
    member_role: str
    member_status: str


class WorkspaceListResponse(BaseModel):
    agencies: list[WorkspaceAgency]
    brands: list[WorkspaceBrand]


class WorkspaceContextResponse(BaseModel):
    agency_id: uuid.UUID
    agency_name: str
    agency_slug: str
    agency_status: str
    user_role: str
    user_status: str
    permissions: list[str]

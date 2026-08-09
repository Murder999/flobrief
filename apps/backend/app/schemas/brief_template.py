from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import FieldType

FIELDS_REQUIRING_OPTIONS = {FieldType.SELECT.value, FieldType.MULTI_SELECT.value}


# ── Industry ────────────────────────────────────────────────────────────────


class IndustryRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool

    model_config = {"from_attributes": True}


# ── Field ────────────────────────────────────────────────────────────────────


class FieldCreate(BaseModel):
    field_key: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(..., min_length=1, max_length=255)
    help_text: str | None = None
    field_type: str
    is_required: bool = False
    options: dict | None = None
    validation_rules: dict | None = None
    placeholder: str | None = None
    sort_order: int = 0

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, v: str) -> str:
        valid = {ft.value for ft in FieldType}
        if v not in valid:
            raise ValueError(f"Invalid field_type '{v}'. Must be one of: {sorted(valid)}")
        return v

    @model_validator(mode="after")
    def check_options_required(self) -> FieldCreate:
        if self.field_type in FIELDS_REQUIRING_OPTIONS and not self.options:
            raise ValueError(f"options is required for field_type '{self.field_type}'")
        return self


class FieldUpdate(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=255)
    help_text: str | None = None
    field_type: str | None = None
    is_required: bool | None = None
    options: dict | None = None
    validation_rules: dict | None = None
    placeholder: str | None = None
    sort_order: int | None = None

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        valid = {ft.value for ft in FieldType}
        if v not in valid:
            raise ValueError(f"Invalid field_type '{v}'.")
        return v


class FieldRead(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    field_key: str
    label: str
    help_text: str | None
    field_type: str
    is_required: bool
    options: dict | None
    validation_rules: dict | None
    placeholder: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReorderFieldsRequest(BaseModel):
    ordered_ids: list[uuid.UUID] = Field(..., min_length=1)


# ── Section ──────────────────────────────────────────────────────────────────


class SectionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    sort_order: int = 0


class SectionUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    sort_order: int | None = None


class SectionRead(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    title: str
    description: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SectionDetail(SectionRead):
    fields: list[FieldRead] = []


class ReorderSectionsRequest(BaseModel):
    ordered_ids: list[uuid.UUID] = Field(..., min_length=1)


# ── Template ──────────────────────────────────────────────────────────────────


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    industry: str | None = Field(None, max_length=100)


class TemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    industry: str | None = Field(None, max_length=100)


class TemplateRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID | None
    name: str
    description: str | None
    industry: str | None
    is_system_template: bool
    is_active: bool
    created_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateDetail(TemplateRead):
    sections: list[SectionDetail] = []

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class BriefTemplateIndustry(BaseModel):
    """Lookup table for industry categories used in template tagging."""

    __tablename__ = "brief_template_industries"
    __table_args__ = (Index("ix_industry_code", "code"),)

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<BriefTemplateIndustry code={self.code}>"


class BriefTemplate(BaseModel):
    """
    A brief template defines the structure of a brief form.
    system templates have agency_id=NULL and is_system_template=True.
    Agency templates are scoped to a specific agency.
    """

    __tablename__ = "brief_templates"
    __table_args__ = (
        Index("ix_brief_template_agency_id", "agency_id"),
        Index("ix_brief_template_industry", "industry"),
    )

    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_system_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<BriefTemplate id={self.id} name={self.name!r}>"


class BriefTemplateSection(BaseModel):
    """An ordered section within a brief template."""

    __tablename__ = "brief_template_sections"
    __table_args__ = (Index("ix_section_template_id", "template_id"),)

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brief_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<BriefTemplateSection id={self.id} title={self.title!r}>"


class BriefTemplateField(BaseModel):
    """A single input field within a brief template section."""

    __tablename__ = "brief_template_fields"
    __table_args__ = (
        UniqueConstraint("section_id", "field_key", name="uq_field_key_per_section"),
        Index("ix_field_section_id", "section_id"),
    )

    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brief_template_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    placeholder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<BriefTemplateField id={self.id} key={self.field_key!r} type={self.field_type}>"

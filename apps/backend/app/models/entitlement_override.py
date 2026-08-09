from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class EntitlementOverride(BaseModel):
    """Per-agency or per-brand override of a Plan limit, set by a platform admin."""

    __tablename__ = "entitlement_overrides"
    __table_args__ = (
        CheckConstraint(
            "(agency_id IS NOT NULL AND brand_id IS NULL)"
            " OR (agency_id IS NULL AND brand_id IS NOT NULL)",
            name="ck_entitlement_override_exactly_one_tenant",
        ),
        UniqueConstraint(
            "agency_id", "brand_id", "limit_key", name="uq_entitlement_override_tenant_key"
        ),
        Index("ix_eo_agency_id", "agency_id"),
        Index("ix_eo_brand_id", "brand_id"),
    )

    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=True,
    )
    limit_key: Mapped[str] = mapped_column(String(50), nullable=False)
    limit_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    def __repr__(self) -> str:
        tenant = f"agency={self.agency_id}" if self.agency_id else f"brand={self.brand_id}"
        return f"<EntitlementOverride {tenant} key={self.limit_key} value={self.limit_value}>"

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class EntitlementUsage(BaseModel):
    """Snapshot of current entitlement usage vs limits for an agency or brand."""

    __tablename__ = "entitlement_usage"

    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    used_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    limit_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<EntitlementUsage key={self.key} used={self.used_value}/{self.limit_value}>"

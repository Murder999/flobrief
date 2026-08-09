import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.models.enums import AgencyStatus


class Agency(BaseModel):
    __tablename__ = "agencies"
    __table_args__ = (Index("ix_agencies_demo_active", "is_demo", "demo_expires_at"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AgencyStatus.ACTIVE.value
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    demo_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    demo_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Agency id={self.id} slug={self.slug} status={self.status}>"

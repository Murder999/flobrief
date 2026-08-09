import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.models.enums import BrandMemberRole, BrandMemberStatus


class BrandMember(BaseModel):
    __tablename__ = "brand_members"
    __table_args__ = (UniqueConstraint("brand_id", "user_id", name="uq_brand_member_brand_user"),)

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(30), nullable=False, default=BrandMemberRole.BRAND_VIEWER.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BrandMemberStatus.INVITED.value
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    def __repr__(self) -> str:
        return f"<BrandMember brand={self.brand_id} user={self.user_id} role={self.role}>"

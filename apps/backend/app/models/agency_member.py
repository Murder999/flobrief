import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.models.enums import AgencyMemberRole, AgencyMemberStatus


class AgencyMember(BaseModel):
    __tablename__ = "agency_members"
    __table_args__ = (
        UniqueConstraint("agency_id", "user_id", name="uq_agency_member_agency_user"),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
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
        String(40), nullable=False, default=AgencyMemberRole.VIEWER.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AgencyMemberStatus.INVITED.value
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    def __repr__(self) -> str:
        return f"<AgencyMember agency={self.agency_id} user={self.user_id} role={self.role}>"

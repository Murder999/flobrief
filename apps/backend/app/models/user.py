from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.models.enums import UserType


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=UserType.AGENCY_USER.value,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )
    job_title: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True, default=None)
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    whatsapp_opt_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    whatsapp_opt_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    # Consent provenance (Part 6B-2) — set only by the consent endpoint, never
    # backfilled for pre-existing opt-ins.
    whatsapp_consent_source: Mapped[str | None] = mapped_column(
        String(30), nullable=True, default=None
    )
    whatsapp_consent_version: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=None
    )

    # No agency_id or brand_id — tenant membership is via AgencyMember / BrandMember tables.
    # platform_admin users have no membership records.

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} type={self.user_type}>"

    @property
    def is_platform_admin(self) -> bool:
        return self.user_type == UserType.PLATFORM_ADMIN.value

    @property
    def normalized_email(self) -> str:
        return self.email.lower()

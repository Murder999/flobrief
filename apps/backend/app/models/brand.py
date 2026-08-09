import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.models.enums import BrandStatus


class Brand(BaseModel):
    __tablename__ = "brands"

    # Nullable to support brand_solo plan (brand without an agency)
    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BrandStatus.ACTIVE.value
    )
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    social_links: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    default_language: Mapped[str] = mapped_column(String(10), nullable=False, default="tr")
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Europe/Istanbul")
    # Finance/billing fields (Part 2 §3) — invoicing currency and tax/billing
    # identity used to snapshot client-invoice billing info at creation time.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")
    billing_address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tax_office: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<Brand id={self.id} slug={self.slug} agency={self.agency_id}>"

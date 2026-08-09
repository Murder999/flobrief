from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.models.enums import PlanCode


class Plan(BaseModel):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        default=PlanCode.STARTER_AGENCY.value,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Prices in smallest currency unit (kuruş for TRY)
    monthly_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    yearly_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")

    # Limits — NULL means unlimited
    max_brands: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_brand_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_brief_templates: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_storage_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_pending_agency_invites: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_pending_brand_invites: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Feature flags
    white_label_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    advanced_reporting_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pdf_export_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    public_report_link_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    whatsapp_infrastructure_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    platform_admin_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<Plan code={self.code} name={self.name}>"

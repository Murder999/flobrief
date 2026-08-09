"""Deterministic sample data for isolated self-service demo tenants."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.brief import Brief
from app.models.brief_template import BriefTemplate, BriefTemplateField, BriefTemplateSection
from app.models.calendar import CalendarItem
from app.models.enums import BriefStatus, CalendarItemStatus, CalendarPlatform, FieldType


async def seed_demo_workspace(
    db: AsyncSession,
    *,
    agency_id: uuid.UUID,
    owner_user_id: uuid.UUID,
) -> None:
    """Create a compact but realistic dashboard, brief and calendar dataset."""
    brands = [
        Brand(
            agency_id=agency_id,
            name="TechNova",
            slug=f"technova-{str(agency_id)[:8]}",
            industry="Teknoloji",
            description="B2B yazılım ürünleri geliştiren büyüme odaklı teknoloji markası.",
        ),
        Brand(
            agency_id=agency_id,
            name="GreenLife",
            slug=f"greenlife-{str(agency_id)[:8]}",
            industry="Sürdürülebilir Yaşam",
            description="Sürdürülebilir tüketim ürünleri ve topluluk platformu.",
        ),
        Brand(
            agency_id=agency_id,
            name="UrbanStyle",
            slug=f"urbanstyle-{str(agency_id)[:8]}",
            industry="Moda",
            description="Şehir yaşamına yönelik çağdaş moda markası.",
        ),
    ]
    db.add_all(brands)
    await db.flush()

    template = BriefTemplate(
        agency_id=agency_id,
        name="Sosyal Medya Kampanyası",
        description="Çok kanallı sosyal medya kampanyaları için örnek brief şablonu.",
        industry="Pazarlama",
        created_by_id=owner_user_id,
        is_active=True,
    )
    db.add(template)
    await db.flush()

    section = BriefTemplateSection(
        template_id=template.id,
        title="Kampanya Detayları",
        description="Hedef, kitle ve teslim kapsamı",
        sort_order=0,
    )
    db.add(section)
    await db.flush()
    db.add_all(
        [
            BriefTemplateField(
                section_id=section.id,
                field_key="campaign_name",
                label="Kampanya Adı",
                field_type=FieldType.TEXT.value,
                is_required=True,
                sort_order=0,
            ),
            BriefTemplateField(
                section_id=section.id,
                field_key="target_audience",
                label="Hedef Kitle",
                field_type=FieldType.TEXTAREA.value,
                is_required=True,
                sort_order=1,
            ),
            BriefTemplateField(
                section_id=section.id,
                field_key="platforms",
                label="Platformlar",
                field_type=FieldType.MULTI_SELECT.value,
                is_required=True,
                options=["Instagram", "LinkedIn", "TikTok", "YouTube"],
                sort_order=2,
            ),
        ]
    )

    today = datetime.now(UTC).date()
    briefs = [
        Brief(
            agency_id=agency_id,
            brand_id=brands[0].id,
            template_id=template.id,
            title="TechNova Ürün Lansmanı",
            description="Yeni analitik modülünün çok kanallı lansman kampanyası.",
            status=BriefStatus.APPROVED.value,
            priority="high",
            deadline=(today + timedelta(days=8)).isoformat(),
            platforms=["LinkedIn", "YouTube"],
            content_types=["video", "social_post"],
            created_by_id=owner_user_id,
        ),
        Brief(
            agency_id=agency_id,
            brand_id=brands[1].id,
            template_id=template.id,
            title="GreenLife Yaz Kampanyası",
            description="Sürdürülebilir yaz alışkanlıkları içerik serisi.",
            status=BriefStatus.IN_REVIEW.value,
            priority="normal",
            deadline=(today + timedelta(days=14)).isoformat(),
            platforms=["Instagram", "TikTok"],
            content_types=["reels", "carousel"],
            created_by_id=owner_user_id,
        ),
        Brief(
            agency_id=agency_id,
            brand_id=brands[2].id,
            template_id=template.id,
            title="UrbanStyle Sonbahar Koleksiyonu",
            description="Yeni koleksiyon için teaser ve lansman içerikleri.",
            status=BriefStatus.REVISION_REQUESTED.value,
            priority="high",
            deadline=(today + timedelta(days=20)).isoformat(),
            platforms=["Instagram"],
            content_types=["photo", "reels"],
            created_by_id=owner_user_id,
        ),
        Brief(
            agency_id=agency_id,
            brand_id=brands[0].id,
            template_id=template.id,
            title="Müşteri Başarı Hikâyesi",
            status=BriefStatus.DRAFT.value,
            priority="normal",
            created_by_id=owner_user_id,
        ),
        Brief(
            agency_id=agency_id,
            brand_id=brands[1].id,
            template_id=template.id,
            title="Topluluk Bülteni",
            status=BriefStatus.SUBMITTED.value,
            priority="low",
            created_by_id=owner_user_id,
        ),
    ]
    db.add_all(briefs)
    await db.flush()

    now = datetime.now(UTC)
    calendar_specs = [
        (brands[0], briefs[0], "Ürün tanıtım videosu", CalendarPlatform.YOUTUBE, 2),
        (brands[0], briefs[0], "Lansman duyurusu", CalendarPlatform.LINKEDIN, 4),
        (brands[1], briefs[1], "Sürdürülebilir yaşam Reels", CalendarPlatform.INSTAGRAM, 6),
        (brands[1], briefs[1], "Topluluk soru-cevap", CalendarPlatform.TIKTOK, 9),
        (brands[2], briefs[2], "Koleksiyon teaser", CalendarPlatform.INSTAGRAM, 12),
        (brands[2], briefs[2], "Lookbook yayını", CalendarPlatform.INSTAGRAM, 16),
    ]
    db.add_all(
        [
            CalendarItem(
                agency_id=agency_id,
                brand_id=brand.id,
                brief_id=brief.id,
                title=title,
                platform=platform.value,
                status=(
                    CalendarItemStatus.SCHEDULED.value
                    if offset <= 9
                    else CalendarItemStatus.PLANNED.value
                ),
                publish_at=now + timedelta(days=offset),
                created_by_id=owner_user_id,
            )
            for brand, brief, title, platform, offset in calendar_specs
        ]
    )

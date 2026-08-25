#!/usr/bin/env python3
"""PostPiloter Demo Seed Script.

Creates a full demo workspace for sales demos and local development.
Idempotent: if demo agency already exists, script exits cleanly.

Usage (run from apps/backend/):
    python scripts/seed_demo.py
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password as get_password_hash  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.agency import Agency  # noqa: E402
from app.models.agency_member import AgencyMember  # noqa: E402
from app.models.brand import Brand  # noqa: E402
from app.models.brief import Brief  # noqa: E402
from app.models.brief_template import (  # noqa: E402
    BriefTemplate,
    BriefTemplateField,
    BriefTemplateSection,
)
from app.models.calendar import CalendarItem  # noqa: E402
from app.models.enums import (  # noqa: E402
    AgencyMemberRole,
    AgencyMemberStatus,
    BriefStatus,
    CalendarItemStatus,
    CalendarPlatform,
    FieldType,
    PlanCode,
    SubscriptionStatus,
)
from app.models.plan import Plan  # noqa: E402
from app.models.subscription import Subscription  # noqa: E402
from app.models.user import User  # noqa: E402

DEMO_AGENCY_SLUG = "demo-agency-flobrief"

DEMO_USERS = [
    {
        "email": "owner@demo.flobrief.com",
        "full_name": "Deniz Yılmaz",
        "password": "Demo1234!",
        "role": AgencyMemberRole.OWNER.value,
    },
    {
        "email": "manager@demo.flobrief.com",
        "full_name": "Arda Şahin",
        "password": "Demo1234!",
        "role": AgencyMemberRole.ADMIN.value,
    },
    {
        "email": "member@demo.flobrief.com",
        "full_name": "Selin Kaya",
        "password": "Demo1234!",
        "role": AgencyMemberRole.BRAND_MANAGER.value,
    },
]

DEMO_BRANDS = [
    {"name": "TechNova", "slug": "technova"},
    {"name": "GreenLife", "slug": "greenlife"},
    {"name": "UrbanStyle", "slug": "urbanstyle"},
]

# 8 rich system templates: (name, description, sections)
# each section: (title, [(key, label, field_type, required, options_list)])
# options_list is a Python list (stored as JSONB) or None
SYSTEM_TEMPLATES = [
    (
        "Sosyal Medya Kampanyası",
        "Instagram, TikTok, X ve diğer platformlar için kapsamlı sosyal medya kampanya brief şablonu.",
        [
            (
                "Kampanya Genel Bilgileri",
                [
                    ("campaign_name", "Kampanya Adı", FieldType.TEXT.value, True, None),
                    (
                        "campaign_objective",
                        "Kampanya Hedefi",
                        FieldType.SELECT.value,
                        True,
                        [
                            "Farkındalık",
                            "Etkileşim",
                            "Satış",
                            "Takipçi Kazanımı",
                            "Web Sitesi Trafiği",
                        ],
                    ),
                    ("target_audience", "Hedef Kitle", FieldType.TEXTAREA.value, True, None),
                    ("age_range", "Yaş Aralığı", FieldType.TEXT.value, False, None),
                    ("platforms", "Platformlar", FieldType.TEXT.value, True, None),
                ],
            ),
            (
                "Bütçe ve Zaman",
                [
                    ("start_date", "Başlangıç Tarihi", FieldType.DATE.value, True, None),
                    ("end_date", "Bitiş Tarihi", FieldType.DATE.value, True, None),
                    ("budget_try", "Toplam Bütçe (TL)", FieldType.NUMBER.value, True, None),
                    (
                        "post_frequency",
                        "Paylaşım Sıklığı",
                        FieldType.SELECT.value,
                        False,
                        ["Günlük", "Haftada 3", "Haftada 1", "2 Haftada 1"],
                    ),
                ],
            ),
            (
                "İçerik ve Mesaj",
                [
                    ("key_message", "Ana Mesaj", FieldType.TEXTAREA.value, True, None),
                    (
                        "tone_of_voice",
                        "Ton",
                        FieldType.SELECT.value,
                        True,
                        ["Profesyonel", "Eğlenceli", "İlham Verici", "Bilgilendirici", "Samimi"],
                    ),
                    ("hashtags", "Hashtag Önerileri", FieldType.TEXT.value, False, None),
                    ("forbidden_topics", "Yasak Konular", FieldType.TEXTAREA.value, False, None),
                    ("cta", "Call to Action", FieldType.TEXT.value, True, None),
                ],
            ),
        ],
    ),
    (
        "Reels & Video İçerik",
        "Instagram Reels, TikTok ve YouTube Shorts için kısa video içerik brief şablonu.",
        [
            (
                "Video Konsepti",
                [
                    ("video_title", "Video Başlığı", FieldType.TEXT.value, True, None),
                    ("concept", "Konsept / Senaryo Özeti", FieldType.TEXTAREA.value, True, None),
                    ("duration_sec", "Süre (saniye)", FieldType.NUMBER.value, True, None),
                    (
                        "video_format",
                        "Format",
                        FieldType.SELECT.value,
                        True,
                        ["Reels", "TikTok", "YouTube Shorts", "Story"],
                    ),
                    ("hook", "İlk 3 Saniye Hook", FieldType.TEXTAREA.value, True, None),
                ],
            ),
            (
                "Prodüksiyon",
                [
                    ("shoot_date", "Çekim Tarihi", FieldType.DATE.value, True, None),
                    ("location", "Çekim Lokasyonu", FieldType.TEXT.value, False, None),
                    ("talent", "Talent / Influencer", FieldType.TEXT.value, False, None),
                    ("music_style", "Müzik Tarzı", FieldType.TEXT.value, False, None),
                    ("caption", "Caption Metni", FieldType.TEXTAREA.value, True, None),
                ],
            ),
        ],
    ),
    (
        "Kozmetik & Beauty Kampanyası",
        "Güzellik, cilt bakımı ve kozmetik ürünleri için özel kampanya brief şablonu.",
        [
            (
                "Ürün Bilgileri",
                [
                    ("product_name", "Ürün Adı", FieldType.TEXT.value, True, None),
                    (
                        "product_category",
                        "Kategori",
                        FieldType.SELECT.value,
                        True,
                        ["Cilt Bakımı", "Makyaj", "Saç Bakımı", "Parfüm", "Vücut Bakımı"],
                    ),
                    (
                        "key_ingredients",
                        "Öne Çıkan İçerikler",
                        FieldType.TEXTAREA.value,
                        False,
                        None,
                    ),
                    (
                        "price_point",
                        "Fiyat Segmenti",
                        FieldType.SELECT.value,
                        False,
                        ["Lüks", "Premium", "Orta Segment", "Ekonomik"],
                    ),
                    ("usp", "Ürün Farklılaşması (USP)", FieldType.TEXTAREA.value, True, None),
                ],
            ),
            (
                "Hedef Kitle & Mesaj",
                [
                    ("target_demo", "Demografik", FieldType.TEXT.value, True, None),
                    ("skin_concern", "Cilt/Güzellik Sorunu", FieldType.TEXTAREA.value, False, None),
                    ("campaign_claim", "Kampanya İddiası", FieldType.TEXT.value, True, None),
                    (
                        "before_after",
                        "Before/After İçerik",
                        FieldType.SELECT.value,
                        False,
                        ["Evet", "Hayır"],
                    ),
                    (
                        "influencer_type",
                        "Influencer Tipi",
                        FieldType.SELECT.value,
                        False,
                        ["Mega (1M+)", "Macro (100K-1M)", "Micro (10K-100K)", "Nano (<10K)"],
                    ),
                ],
            ),
        ],
    ),
    (
        "Sağlık & Klinik İletişimi",
        "Klinik, hastane, sağlık merkezi ve sağlık ürünleri için yasal uyumlu brief şablonu.",
        [
            (
                "Kurum ve Hizmet Bilgisi",
                [
                    ("institution_name", "Kurum Adı", FieldType.TEXT.value, True, None),
                    ("service_type", "Hizmet / Uzmanlık Alanı", FieldType.TEXT.value, True, None),
                    ("target_patient", "Hedef Hasta Profili", FieldType.TEXTAREA.value, True, None),
                    (
                        "accreditations",
                        "Akreditasyon / Sertifikalar",
                        FieldType.TEXT.value,
                        False,
                        None,
                    ),
                    ("legal_disclaimer", "Yasal Uyarı Metni", FieldType.TEXTAREA.value, True, None),
                ],
            ),
            (
                "İçerik Kısıtlamaları",
                [
                    (
                        "forbidden_claims",
                        "Yapılamayacak İddialar",
                        FieldType.TEXTAREA.value,
                        True,
                        None,
                    ),
                    (
                        "approved_visuals",
                        "Onaylanan Görsel Tipleri",
                        FieldType.TEXT.value,
                        False,
                        None,
                    ),
                    (
                        "tone",
                        "İletişim Tonu",
                        FieldType.SELECT.value,
                        True,
                        [
                            "Bilimsel/Akademik",
                            "Sıcak/Güven Verici",
                            "Bilgilendirici",
                            "Motivasyonel",
                        ],
                    ),
                    (
                        "cta",
                        "Yönlendirme (CTA)",
                        FieldType.SELECT.value,
                        True,
                        ["Randevu Al", "Bizi Ara", "Daha Fazla Bilgi", "Ücretsiz Danışma"],
                    ),
                ],
            ),
        ],
    ),
    (
        "E-ticaret & Ürün Lansmanı",
        "Online satış ve ürün lansmanı kampanyaları için dönüşüm odaklı brief şablonu.",
        [
            (
                "Ürün & Kampanya",
                [
                    ("product_name", "Ürün / Koleksiyon Adı", FieldType.TEXT.value, True, None),
                    ("launch_date", "Lansman Tarihi", FieldType.DATE.value, True, None),
                    (
                        "campaign_type",
                        "Kampanya Tipi",
                        FieldType.SELECT.value,
                        True,
                        ["Yeni Ürün", "Sezon Sonu", "Flash Satış", "Bundle Teklifi", "Abonelik"],
                    ),
                    ("discount_rate", "İndirim Oranı (%)", FieldType.NUMBER.value, False, None),
                    ("stock_limit", "Stok Kısıtlaması", FieldType.TEXT.value, False, None),
                ],
            ),
            (
                "Pazarlama Kanalları",
                [
                    (
                        "primary_channel",
                        "Ana Kanal",
                        FieldType.SELECT.value,
                        True,
                        ["Instagram", "TikTok", "Google Ads", "Email", "Meta Ads", "YouTube"],
                    ),
                    (
                        "secondary_channels",
                        "Destekleyici Kanallar",
                        FieldType.TEXT.value,
                        False,
                        None,
                    ),
                    (
                        "retargeting",
                        "Retargeting",
                        FieldType.SELECT.value,
                        False,
                        ["Evet", "Hayır"],
                    ),
                    ("landing_page_url", "Landing Page URL", FieldType.TEXT.value, False, None),
                    ("conversion_goal", "Dönüşüm Hedefi", FieldType.TEXTAREA.value, True, None),
                ],
            ),
        ],
    ),
    (
        "Web Sitesi & Dijital Proje",
        "Web sitesi yenileme, landing page ve dijital ürün projeleri için brief şablonu.",
        [
            (
                "Proje Kapsamı",
                [
                    ("project_name", "Proje Adı", FieldType.TEXT.value, True, None),
                    (
                        "project_type",
                        "Proje Tipi",
                        FieldType.SELECT.value,
                        True,
                        ["Yeni Web Sitesi", "Yenileme", "Landing Page", "E-ticaret", "Web App"],
                    ),
                    ("page_count", "Sayfa Sayısı (Tahmini)", FieldType.NUMBER.value, False, None),
                    ("deadline", "Teslim Tarihi", FieldType.DATE.value, True, None),
                    ("budget_try", "Bütçe (TL)", FieldType.NUMBER.value, True, None),
                ],
            ),
            (
                "Teknik Gereksinimler",
                [
                    (
                        "cms",
                        "CMS / Platform",
                        FieldType.SELECT.value,
                        False,
                        ["WordPress", "Webflow", "Next.js", "Shopify", "Özel Geliştirme"],
                    ),
                    ("integrations", "Entegrasyonlar", FieldType.TEXTAREA.value, False, None),
                    (
                        "seo_required",
                        "SEO Optimizasyonu",
                        FieldType.SELECT.value,
                        False,
                        ["Evet", "Hayır"],
                    ),
                    (
                        "mobile_priority",
                        "Mobil Öncelik",
                        FieldType.SELECT.value,
                        True,
                        ["Evet, önce mobil", "Desktop öncelikli", "Her ikisi eşit"],
                    ),
                    (
                        "reference_sites",
                        "Referans Web Siteleri",
                        FieldType.TEXTAREA.value,
                        False,
                        None,
                    ),
                ],
            ),
        ],
    ),
    (
        "Kurumsal Kimlik & Marka",
        "Logo tasarımı, kurumsal kimlik ve marka rehberi projeleri için brief şablonu.",
        [
            (
                "Marka Bilgileri",
                [
                    ("brand_name", "Marka Adı", FieldType.TEXT.value, True, None),
                    ("industry", "Sektör", FieldType.TEXT.value, True, None),
                    ("brand_values", "Marka Değerleri", FieldType.TEXTAREA.value, True, None),
                    ("target_audience", "Hedef Kitle", FieldType.TEXTAREA.value, True, None),
                    ("competitors", "Rakipler", FieldType.TEXT.value, False, None),
                ],
            ),
            (
                "Tasarım Yönü",
                [
                    (
                        "style_direction",
                        "Tasarım Yönü",
                        FieldType.SELECT.value,
                        True,
                        [
                            "Minimal",
                            "Modern",
                            "Klasik",
                            "Canlı/Renkli",
                            "Kurumsal",
                            "Sıcak/Organik",
                        ],
                    ),
                    ("color_preferences", "Renk Tercihleri", FieldType.TEXTAREA.value, False, None),
                    (
                        "fonts_to_avoid",
                        "Kaçınılacak Font/Renk",
                        FieldType.TEXTAREA.value,
                        False,
                        None,
                    ),
                    ("deliverables", "Teslim Edilecekler", FieldType.TEXTAREA.value, True, None),
                    ("deadline", "Teslim Tarihi", FieldType.DATE.value, True, None),
                ],
            ),
        ],
    ),
    (
        "Influencer & İçerik Üretici",
        "Influencer iş birlikleri ve içerik üreticisi anlaşmaları için brief şablonu.",
        [
            (
                "İş Birliği Detayları",
                [
                    ("brand_name", "Marka Adı", FieldType.TEXT.value, True, None),
                    (
                        "campaign_name",
                        "Kampanya / Kolaborasyon Adı",
                        FieldType.TEXT.value,
                        True,
                        None,
                    ),
                    ("influencer_name", "Influencer Adı / Hesap", FieldType.TEXT.value, True, None),
                    (
                        "collaboration_type",
                        "İş Birliği Tipi",
                        FieldType.SELECT.value,
                        True,
                        [
                            "Sponsored Post",
                            "Uzun Vadeli Elçi",
                            "Ürün Gönderimi",
                            "Barter",
                            "Paid Partnership",
                        ],
                    ),
                    (
                        "deliverables",
                        "Teslim Edilecek İçerikler",
                        FieldType.TEXTAREA.value,
                        True,
                        None,
                    ),
                ],
            ),
            (
                "İçerik Gereksinimleri",
                [
                    (
                        "key_message",
                        "İletilmesi Gereken Mesaj",
                        FieldType.TEXTAREA.value,
                        True,
                        None,
                    ),
                    ("mandatory_mentions", "Zorunlu Bahsetmeler", FieldType.TEXT.value, True, None),
                    ("forbidden_content", "Yasak İçerik", FieldType.TEXTAREA.value, False, None),
                    ("post_deadline", "Paylaşım Tarihi", FieldType.DATE.value, True, None),
                    (
                        "approval_required",
                        "Ön Onay Gerekli mi",
                        FieldType.SELECT.value,
                        True,
                        [
                            "Evet, içerik onaylanmadan yayınlanamaz",
                            "Hayır, doğrudan yayınlayabilir",
                        ],
                    ),
                ],
            ),
        ],
    ),
]


async def seed_system_templates(session) -> int:
    """Seed system templates if they don't exist. Returns number created."""
    existing = await session.scalar(
        select(BriefTemplate).where(BriefTemplate.is_system_template.is_(True))
    )
    if existing is not None:
        print("[SKIP] System templates already exist.")
        return 0

    created = 0
    for name, description, sections_data in SYSTEM_TEMPLATES:
        tmpl = BriefTemplate(
            id=uuid.uuid4(),
            agency_id=None,
            name=name,
            description=description,
            created_by_id=None,
            is_system_template=True,
            is_active=True,
        )
        session.add(tmpl)
        await session.flush()

        for sec_order, (sec_title, fields_data) in enumerate(sections_data):
            sec = BriefTemplateSection(
                id=uuid.uuid4(),
                template_id=tmpl.id,
                title=sec_title,
                sort_order=sec_order,
            )
            session.add(sec)
            await session.flush()

            for fld_order, (key, label, ftype, required, options_json) in enumerate(fields_data):
                fld = BriefTemplateField(
                    id=uuid.uuid4(),
                    section_id=sec.id,
                    field_key=key,
                    label=label,
                    field_type=ftype,
                    is_required=required,
                    sort_order=fld_order,
                    options=options_json,
                )
                session.add(fld)

        created += 1

    await session.commit()
    print(f"[OK] {created} system templates created.")
    return created


async def seed_demo() -> None:
    async with AsyncSessionLocal() as session:
        # ── System Templates ──────────────────────────────────────────────────
        await seed_system_templates(session)

        # Idempotency check for demo agency
        existing = await session.scalar(select(Agency).where(Agency.slug == DEMO_AGENCY_SLUG))
        if existing is not None:
            print("[SKIP] Demo agency already exists.")
            return

        # ── Agency ────────────────────────────────────────────────────────────
        agency = Agency(
            id=uuid.uuid4(),
            name="Demo Agency",
            slug=DEMO_AGENCY_SLUG,
        )
        session.add(agency)
        await session.flush()

        # ── Users & Members ───────────────────────────────────────────────────
        user_objs: list[User] = []
        for ud in DEMO_USERS:
            user = User(
                id=uuid.uuid4(),
                email=ud["email"],
                full_name=ud["full_name"],
                password_hash=get_password_hash(ud["password"]),
                is_active=True,
                is_verified=True,
            )
            session.add(user)
            await session.flush()

            member = AgencyMember(
                id=uuid.uuid4(),
                agency_id=agency.id,
                user_id=user.id,
                role=ud["role"],
                status=AgencyMemberStatus.ACTIVE.value,
                joined_at=datetime.now(UTC),
            )
            session.add(member)
            user_objs.append(user)

        await session.flush()

        # ── Brands ────────────────────────────────────────────────────────────
        brand_objs: list[Brand] = []
        for bd in DEMO_BRANDS:
            brand = Brand(
                id=uuid.uuid4(),
                agency_id=agency.id,
                name=bd["name"],
                slug=bd["slug"],
            )
            session.add(brand)
            brand_objs.append(brand)
        await session.flush()

        # ── Brief Template (agency-scoped demo) ───────────────────────────────
        template = BriefTemplate(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name="Sosyal Medya Kampanyası",
            description="Sosyal medya kampanyaları için standart brief şablonu.",
            created_by_id=user_objs[0].id,
            is_active=True,
        )
        session.add(template)
        await session.flush()

        section = BriefTemplateSection(
            id=uuid.uuid4(),
            template_id=template.id,
            title="Kampanya Detayları",
            sort_order=0,
        )
        session.add(section)
        await session.flush()

        fields = [
            ("campaign_name", "Kampanya Adı", FieldType.TEXT.value, True),
            ("target_audience", "Hedef Kitle", FieldType.TEXTAREA.value, True),
            ("message_tone", "Mesaj Tonu", FieldType.SELECT.value, False),
            ("start_date", "Başlangıç Tarihi", FieldType.DATE.value, True),
            ("budget_try", "Bütçe (TL)", FieldType.NUMBER.value, False),
        ]
        for i, (key, label, ftype, required) in enumerate(fields):
            session.add(
                BriefTemplateField(
                    id=uuid.uuid4(),
                    section_id=section.id,
                    field_key=key,
                    label=label,
                    field_type=ftype,
                    is_required=required,
                    sort_order=i,
                )
            )

        # ── Briefs ────────────────────────────────────────────────────────────
        brief_configs = [
            (brand_objs[0], "TechNova Q3 Sosyal Medya", BriefStatus.APPROVED.value, "high"),
            (brand_objs[1], "GreenLife Yaz Kampanyası", BriefStatus.IN_REVIEW.value, "normal"),
            (brand_objs[2], "UrbanStyle Koleksiyon Lansmanı", BriefStatus.DRAFT.value, "low"),
            (brand_objs[0], "TechNova Ürün Demosu", BriefStatus.DRAFT.value, "normal"),
            (brand_objs[1], "GreenLife İçerik Planı", BriefStatus.REVISION_REQUESTED.value, "high"),
        ]
        for brand, title, status, priority in brief_configs:
            session.add(
                Brief(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    brand_id=brand.id,
                    template_id=template.id,
                    title=title,
                    status=status,
                    priority=priority,
                    created_by_id=user_objs[1].id,
                )
            )

        # ── Calendar Items ────────────────────────────────────────────────────
        now = datetime.now(UTC)
        scheduled = CalendarItemStatus.SCHEDULED.value
        planned = CalendarItemStatus.PLANNED.value
        published = CalendarItemStatus.PUBLISHED.value
        ig = CalendarPlatform.INSTAGRAM.value
        li = CalendarPlatform.LINKEDIN.value
        x = CalendarPlatform.X.value
        fb = CalendarPlatform.FACEBOOK.value
        tt = CalendarPlatform.TIKTOK.value
        calendar_configs = [
            (brand_objs[0], "Instagram Reels — Ürün Tanıtımı", ig, scheduled, 1),
            (brand_objs[0], "LinkedIn Makale", li, planned, 3),
            (brand_objs[1], "X Kampanya Başlangıcı", x, published, -2),
            (brand_objs[1], "Facebook Story Serisi", fb, scheduled, 7),
            (brand_objs[2], "TikTok Unboxing Video", tt, planned, 5),
            (brand_objs[2], "Instagram Feed Post", ig, scheduled, 10),
        ]
        for brand, title, platform, status, day_offset in calendar_configs:
            session.add(
                CalendarItem(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    brand_id=brand.id,
                    title=title,
                    platform=platform,
                    status=status,
                    publish_at=now + timedelta(days=day_offset),
                    created_by_id=user_objs[1].id,
                )
            )

        # ── Subscription ──────────────────────────────────────────────────────
        plan = await session.scalar(select(Plan).where(Plan.code == PlanCode.PRO_AGENCY.value))
        if plan:
            sub = Subscription(
                id=uuid.uuid4(),
                agency_id=agency.id,
                plan_id=plan.id,
                status=SubscriptionStatus.ACTIVE.value,
                billing_provider="manual",
                current_period_start=now,
                current_period_end=now + timedelta(days=365),
            )
            session.add(sub)
        else:
            print("[WARN] pro_agency plan not found — run `make seed` first.")

        await session.commit()
        print(
            "[OK] Demo seed complete.\n"
            "     Agency:  Demo Agency\n"
            "     Owner:   owner@demo.flobrief.com  /  Demo1234!\n"
            "     Manager: manager@demo.flobrief.com / Demo1234!\n"
            "     Member:  member@demo.flobrief.com  / Demo1234!\n"
            f"     Brands:  {', '.join(b.name for b in brand_objs)}\n"
            "     Briefs:  5 (approved, in_review, draft, revision_requested)\n"
            "     Calendar: 6 items"
        )


if __name__ == "__main__":
    asyncio.run(seed_demo())

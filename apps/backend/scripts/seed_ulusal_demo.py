#!/usr/bin/env python3
"""Ulusal Faktoring demo seed script.

Creates a controlled, re-runnable demo dataset for the "360 Stradigi" agency
and its "Ulusal Faktoring" brand: real auth accounts (real password hashing,
real JWT-compatible users), real agency/brand membership rows, a brand DNA
profile, and six detailed social-media briefs across the full brief
lifecycle (draft -> in_production -> ready_for_review -> revision_requested
-> approved), including one deliverable with image annotations (2 open,
1 resolved with an agency + brand reply).

Local/dev only. Refuses to run against anything that isn't APP_ENV=development
and a localhost database — see `_assert_safe_environment()`.

Idempotent: safe to re-run. Existing rows (matched by natural key: agency
slug, brand slug, user email, brief title) are updated in place rather than
duplicated.

Usage (run from apps/backend/, with the local dev Postgres container up):
    python -m scripts.seed_ulusal_demo
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
import uuid
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.agency import Agency  # noqa: E402
from app.models.agency_member import AgencyMember  # noqa: E402
from app.models.approval import Approval  # noqa: E402
from app.models.asset import Asset, AssetLink  # noqa: E402
from app.models.brand import Brand  # noqa: E402
from app.models.brand_identity import BrandIdentityProfile  # noqa: E402
from app.models.brand_member import BrandMember  # noqa: E402
from app.models.brief import Brief, BriefAssignee  # noqa: E402
from app.models.deliverable import Deliverable  # noqa: E402
from app.models.deliverable_annotation import (  # noqa: E402
    AnnotationReply,
    DeliverableAnnotation,
)
from app.models.enums import (  # noqa: E402
    AgencyMemberRole,
    AgencyMemberStatus,
    AgencyStatus,
    ApprovalStatus,
    BrandMemberRole,
    BrandMemberStatus,
    BrandStatus,
    PlanCode,
    SubscriptionStatus,
    UserType,
)
from app.models.plan import Plan  # noqa: E402
from app.models.subscription import Subscription  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.brief import default_caps_for_role  # noqa: E402
from app.services.storage_service import get_storage_backend, normalize_filename  # noqa: E402

# ── Safety guard ──────────────────────────────────────────────────────────────

_ALLOWED_DB_HOSTS = {"localhost", "127.0.0.1"}


def _assert_safe_environment() -> None:
    """Abort before opening any DB session unless this is unmistakably local/dev."""
    if settings.is_production:
        print(f"[ABORT] APP_ENV={settings.APP_ENV!r}. Refusing to run against production.")
        sys.exit(1)

    host = urlsplit(settings.DATABASE_URL.replace("+asyncpg", "")).hostname
    if host not in _ALLOWED_DB_HOSTS:
        print(f"[ABORT] DATABASE_URL host {host!r} is not localhost. Refusing to run.")
        sys.exit(1)

    print(f"[OK] Environment check passed (APP_ENV={settings.APP_ENV}, DB host={host}).")


# ── Constants ─────────────────────────────────────────────────────────────────

AGENCY_NAME = "360 Stradigi"
AGENCY_SLUG = "360-stradigi"
BRAND_NAME = "Ulusal Faktoring"
BRAND_SLUG = "ulusal-faktoring"
DEMO_PASSWORD = "159951.efe."  # noqa: S105 — demo-only credential, documented in final report

TODAY = datetime.now(UTC).date()


def _d(offset_days: int) -> str:
    return (TODAY + timedelta(days=offset_days)).strftime("%Y-%m-%d")


AGENCY_USERS = [
    {
        "email": "efe@360stradigi.com",
        "full_name": "Efe",
        "agency_role": AgencyMemberRole.OWNER.value,
    },
    {
        "email": "tasarım@360stradigi.com",
        "full_name": "Tasarımcı",
        "agency_role": AgencyMemberRole.DESIGNER.value,
    },
    {
        "email": "sosya@360stradigi.com",
        "full_name": "Sosyal Medya Uzmanı",
        "agency_role": AgencyMemberRole.SOCIAL_MEDIA_MANAGER.value,
    },
]

BRAND_USER = {
    "email": "info@ulusal.com",
    "full_name": "Ulusal Faktoring Marka Yöneticisi",
    "brand_role": BrandMemberRole.BRAND_MANAGER.value,
}

_REFERENCE_NOTE = (
    "Marka DNA profilindeki #052562 ana rengi ve Montserrat tipografisi referans alınmalıdır."
)
_ADDITIONAL_NOTE = (
    "Yayın öncesi yalnızca marka onayı yeterlidir; ayrı bir hukuk/uyumluluk onayı gerekmez."
)

BRIEFS = [
    {
        "title": "Nakit Akışınızı Güçlendirin",
        "content_types": ["Instagram gönderisi", "LinkedIn gönderisi"],
        "platforms": ["instagram", "linkedin"],
        "purpose": (
            "İşletmelerin vadeli alacaklarını beklemeden nakde dönüştürebileceğini sade ve "
            "güvenilir biçimde anlatmak."
        ),
        "audience": "KOBİ sahipleri, finans yöneticileri, işletme yöneticileri",
        "key_message": (
            "Vadeli alacaklarınızı nakde dönüştürerek işletmenizin nakit akışını daha güçlü ve "
            "öngörülebilir hale getirin."
        ),
        "suggested_copy": (
            "Nakit akışınızı planlamak için vadelerin dolmasını beklemek zorunda değilsiniz. "
            "Ulusal Faktoring ile ticari alacaklarınızı işletmenizin ihtiyaçlarına uygun "
            "biçimde değerlendirin."
        ),
        "cta": "Çözümlerimizi keşfedin.",
        "visual_direction": (
            "Kurumsal fakat sıradan banka reklamı gibi görünmeyen premium sosyal medya tasarımı. "
            "Koyu lacivert zemin, kontrollü veri akışı veya finansal hareket çizgileri, geniş "
            "negatif alan ve güçlü tipografi."
        ),
        "dimensions": "1080x1350 Instagram, 1200x1200 LinkedIn",
        "priority": "high",
        "assignee_email": "sosya@360stradigi.com",
        "participant_role": "social_media_manager",
        "status": "draft",
        "dates": {
            "start": _d(4), "draft": _d(8), "feedback": _d(11), "deadline": _d(14),
            "publish": _d(18),
        },
        "reference_notes": _REFERENCE_NOTE,
        "additional_notes": _ADDITIONAL_NOTE,
    },
    {
        "title": "Alacaklar Beklemesin, İşiniz İlerlesin",
        "content_types": ["Instagram carousel"],
        "platforms": ["instagram"],
        "purpose": "Faktoring sürecini 4 sade adımda açıklamak.",
        "content_flow": [
            "Vadeli satış yaptınız.",
            "Faturanızı ve alacağınızı değerlendirmeye sundunuz.",
            "Uygun finansman çözümü oluşturuldu.",
            "İşletmenizin nakit akışı desteklendi.",
        ],
        "key_message": "Faktoring karmaşık olmak zorunda değil.",
        "cta": "Süreci yakından inceleyin.",
        "visual_direction": (
            "Her slaytta tek ana fikir, temiz infografik, Montserrat tipografi, #052562 ana "
            "renk. Stok para fotoğrafları, el sıkışma klişeleri ve yapay 3D ikonlardan "
            "kaçınılsın."
        ),
        "dimensions": "5 adet 1080x1350 carousel",
        "priority": "normal",
        "assignee_email": "tasarım@360stradigi.com",
        "participant_role": "designer",
        "status": "draft",
        "dates": {
            "start": _d(6), "draft": _d(10), "feedback": _d(13), "deadline": _d(16),
            "publish": _d(20),
        },
        "reference_notes": _REFERENCE_NOTE,
        "additional_notes": _ADDITIONAL_NOTE,
    },
    {
        "title": "KOBİ'ler İçin Daha Planlı Finansman",
        "content_types": ["LinkedIn gönderisi", "Kurumsal görsel"],
        "platforms": ["linkedin"],
        "purpose": (
            "Ulusal Faktoring'i KOBİ'lerin büyüme ve nakit planlama süreçlerinde güvenilir "
            "çözüm ortağı olarak konumlandırmak."
        ),
        "audience": "KOBİ sahipleri, CFO'lar, finans müdürleri",
        "key_message": "Güçlü işletmeler yalnızca satışlarını değil, nakit akışlarını da planlar.",
        "suggested_copy": (
            "Büyüme hedeflerinizi destekleyen finansal yapı, öngörülebilir bir nakit akışıyla "
            "başlar. Ulusal Faktoring, ticari alacakların işletme sermayesine dönüşmesini "
            "destekleyen çözümler sunar."
        ),
        "cta": "İşletmenize uygun çözümler hakkında bilgi alın.",
        "visual_direction": (
            "Kurumsal rapor estetiği, sade veri görselleştirme, premium editorial kompozisyon."
        ),
        "dimensions": "1200x1200",
        "priority": "high",
        "assignee_email": "sosya@360stradigi.com",
        "participant_role": "social_media_manager",
        "status": "in_production",
        "dates": {
            "start": _d(2), "draft": _d(9), "feedback": _d(12), "deadline": _d(15),
            "publish": _d(19),
        },
        "reference_notes": _REFERENCE_NOTE,
        "additional_notes": _ADDITIONAL_NOTE,
    },
    {
        "title": "Faktoring Nedir?",
        "content_types": ["Instagram carousel", "Instagram story"],
        "platforms": ["instagram"],
        "purpose": "Faktoring kavramını sektörel jargon kullanmadan açıklamak.",
        "content_flow": [
            "Faktoring nedir?",
            "Hangi işletmeler faydalanabilir?",
            "Vadeli alacaklar nasıl değerlendirilir?",
            "Süreçte hangi belgeler gerekir?",
            "İşletmenin nakit planına nasıl katkı sağlar?",
        ],
        "tone": "Eğitici, sakin, güven veren",
        "cta": "Sorularınız için bizimle iletişime geçin.",
        "visual_direction": (
            "Soru-cevap kartları, yüksek okunabilirlik, kontrollü ikonografi, mobilde kolay "
            "taranabilir yapı."
        ),
        "dimensions": "5 adet 1080x1350 carousel, 3 adet 1080x1920 story",
        "priority": "normal",
        "assignee_email": "tasarım@360stradigi.com",
        "participant_role": "designer",
        "status": "ready_for_review",
        "dates": {
            "start": _d(1), "draft": _d(5), "feedback": _d(7), "deadline": _d(10),
            "publish": _d(21),
        },
        "reference_notes": _REFERENCE_NOTE,
        "additional_notes": _ADDITIONAL_NOTE,
    },
    {
        "title": "İşletmenizin Zamanı Değerli",
        "content_types": ["Kısa motion video / Reels"],
        "platforms": ["instagram", "linkedin"],
        "purpose": (
            "Vadeli alacak nedeniyle bekleyen işletme süreçlerini dinamik ama güvenilir bir "
            "anlatımla göstermek."
        ),
        "content_flow": [
            "Bekleyen fatura veya takvim detayı",
            "Nakit akışındaki gecikmenin soyut gösterimi",
            "Sürecin hızlanması",
            "İşletmenin üretim, tedarik veya büyüme adımlarına devam etmesi",
            "Ulusal Faktoring kapanış ekranı",
        ],
        "key_message": "Zamanınızı beklemeye değil, işinizi büyütmeye ayırın.",
        "cta": "Ulusal Faktoring çözümlerini keşfedin.",
        "duration": "15–20 saniye",
        "visual_direction": (
            "Gerçek kurumsal iş ortamı, doğal hareketler, yapay zekâ veya stok video hissi "
            "vermeyen görüntüler. Abartılı para animasyonu kullanılmasın."
        ),
        "dimensions": "1080x1920 dikey video ve 1080x1080 kare uyarlama",
        "priority": "high",
        "assignee_email": "tasarım@360stradigi.com",
        "participant_role": "designer",
        "status": "revision_requested",
        "dates": {
            "start": _d(1), "draft": _d(4), "feedback": _d(6), "deadline": _d(9),
            "publish": _d(25),
        },
        "reference_notes": _REFERENCE_NOTE,
        "additional_notes": _ADDITIONAL_NOTE,
        "has_demo_deliverable": True,
    },
    {
        "title": "30 Ağustos Zafer Bayramı Kutlama İçeriği",
        "content_types": ["Özel gün gönderisi", "Instagram story"],
        "platforms": ["instagram", "linkedin"],
        "purpose": (
            "30 Ağustos Zafer Bayramı'nı markanın kurumsal kimliğine uygun, saygılı ve güçlü "
            "bir tasarımla kutlamak."
        ),
        "key_message": "30 Ağustos Zafer Bayramımız Kutlu Olsun.",
        "suggested_copy": (
            "Başta Gazi Mustafa Kemal Atatürk olmak üzere bağımsızlığımız için mücadele eden "
            "tüm kahramanlarımızı saygı ve minnetle anıyoruz."
        ),
        "visual_direction": (
            "Minimal, premium ve saygılı. Türk bayrağı veya kırmızı vurgu kontrollü "
            "kullanılabilir. Ana marka laciverti korunmalı. Aşırı efekt, kalabalık kompozisyon "
            "ve sıradan hazır şablon görünümünden kaçınılsın."
        ),
        "dimensions": "1080x1350 gönderi, 1080x1920 story, 1200x1200 LinkedIn",
        "priority": "high",
        "assignee_email": "tasarım@360stradigi.com",
        "participant_role": "designer",
        "status": "approved",
        "dates": {
            "start": "2026-08-01", "draft": "2026-08-10", "feedback": "2026-08-15",
            "deadline": "2026-08-25", "publish": "2026-08-30",
        },
        "reference_notes": _REFERENCE_NOTE,
        "additional_notes": _ADDITIONAL_NOTE,
    },
]

_APPROVAL_STATUS_FOR_BRIEF_STATUS = {
    "ready_for_review": ApprovalStatus.PENDING.value,
    "revision_requested": ApprovalStatus.REVISION_REQUESTED.value,
    "approved": ApprovalStatus.APPROVED.value,
}


# ── Idempotent get-or-create helpers ──────────────────────────────────────────

async def _get_or_create_agency(session) -> tuple[Agency, bool]:
    result = await session.execute(
        select(Agency).where(Agency.slug == AGENCY_SLUG, Agency.deleted_at.is_(None))
    )
    agency = result.scalar_one_or_none()
    if agency is not None:
        agency.name = AGENCY_NAME
        agency.status = AgencyStatus.ACTIVE.value
        return agency, False

    agency = Agency(
        id=uuid.uuid4(), name=AGENCY_NAME, slug=AGENCY_SLUG, status=AgencyStatus.ACTIVE.value
    )
    session.add(agency)
    await session.flush()
    return agency, True


async def _get_or_create_user(session, email: str, full_name: str, user_type: str) -> tuple[User, bool]:
    result = await session.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if user is not None:
        user.password_hash = hash_password(DEMO_PASSWORD)
        user.full_name = full_name
        user.user_type = user_type
        user.is_active = True
        user.is_verified = True
        user.deleted_at = None
        return user, False

    user = User(
        id=uuid.uuid4(),
        email=email.lower(),
        password_hash=hash_password(DEMO_PASSWORD),
        full_name=full_name,
        user_type=user_type,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    return user, True


async def _get_or_create_agency_member(session, agency_id, user_id, role: str) -> tuple[AgencyMember, bool]:
    result = await session.execute(
        select(AgencyMember).where(
            AgencyMember.agency_id == agency_id,
            AgencyMember.user_id == user_id,
            AgencyMember.deleted_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    if member is not None:
        member.role = role
        member.status = AgencyMemberStatus.ACTIVE.value
        member.joined_at = member.joined_at or datetime.now(UTC)
        return member, False

    member = AgencyMember(
        id=uuid.uuid4(), agency_id=agency_id, user_id=user_id, role=role,
        status=AgencyMemberStatus.ACTIVE.value, joined_at=datetime.now(UTC),
    )
    session.add(member)
    await session.flush()
    return member, True


async def _get_or_create_brand(session, agency_id) -> tuple[Brand, bool]:
    result = await session.execute(
        select(Brand).where(
            Brand.slug == BRAND_SLUG, Brand.agency_id == agency_id, Brand.deleted_at.is_(None)
        )
    )
    brand = result.scalar_one_or_none()
    if brand is not None:
        brand.name = BRAND_NAME
        brand.status = BrandStatus.ACTIVE.value
        return brand, False

    brand = Brand(
        id=uuid.uuid4(),
        agency_id=agency_id,
        name=BRAND_NAME,
        slug=BRAND_SLUG,
        status=BrandStatus.ACTIVE.value,
        industry="Finansal hizmetler / Faktoring",
        description=(
            "Ulusal Faktoring, işletmelerin vadeli alacaklarını hızlı ve sürdürülebilir nakit "
            "akışına dönüştürmesine yardımcı olan kurumsal bir finansal hizmet markasıdır."
        ),
        contact_email=BRAND_USER["email"],
    )
    session.add(brand)
    await session.flush()
    return brand, True


async def _get_or_create_brand_member(session, brand_id, user_id, role: str) -> tuple[BrandMember, bool]:
    result = await session.execute(
        select(BrandMember).where(
            BrandMember.brand_id == brand_id,
            BrandMember.user_id == user_id,
            BrandMember.deleted_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    if member is not None:
        member.role = role
        member.status = BrandMemberStatus.ACTIVE.value
        member.joined_at = member.joined_at or datetime.now(UTC)
        return member, False

    member = BrandMember(
        id=uuid.uuid4(), brand_id=brand_id, user_id=user_id, role=role,
        status=BrandMemberStatus.ACTIVE.value, joined_at=datetime.now(UTC),
    )
    session.add(member)
    await session.flush()
    return member, True


async def _get_or_create_brand_identity(session, brand_id, agency_id, approver: User) -> tuple[BrandIdentityProfile, bool]:
    result = await session.execute(
        select(BrandIdentityProfile).where(
            BrandIdentityProfile.brand_id == brand_id,
            BrandIdentityProfile.deleted_at.is_(None),
        )
    )
    profile = result.scalar_one_or_none()
    now = datetime.now(UTC)

    fields = {
        "summary": (
            "Ulusal Faktoring; KOBİ'lere, işletme sahiplerine ve finans yöneticilerine yönelik, "
            "güven veren, kurumsal ve anlaşılır bir sosyal medya iletişimi kullanır."
        ),
        "primary_colors": [
            {"name": "Ana Lacivert", "hex": "#052562", "usage": "Logo, başlıklar, ana zemin"}
        ],
        "secondary_colors": [
            {"name": "Beyaz", "hex": "#FFFFFF", "usage": "Zemin ve negatif alan"},
            {"name": "Açık Gri", "hex": "#E5E7EB", "usage": "Destekleyici yüzeyler"},
            {"name": "Kontrollü Turkuaz", "hex": "#0FB5AE", "usage": "Vurgu ve CTA elemanları"},
        ],
        "typography": [
            {"role": "primary", "family": "Montserrat", "weight": "600",
             "usage": "Başlıklar ve CTA"},
            {"role": "secondary", "family": "Montserrat", "weight": "400",
             "usage": "Gövde metni"},
        ],
        "tone_of_voice": {
            "summary": "Güven veren, kurumsal, anlaşılır, modern",
            "avoid": "Kesin kazanç vaadi, yanıltıcı finansal iddia, aşırı satış dili",
            "audience": "KOBİ'ler, işletme sahipleri, finans yöneticileri ve ticari şirketler",
        },
        "do_rules": [
            "Sade ve anlaşılır dil kullan",
            "Kurumsal güven hissi ver",
            "Veriye dayalı ifadeler tercih et",
        ],
        "dont_rules": [
            "Kesin kazanç vaadi verme",
            "Yanıltıcı finansal iddialarda bulunma",
            "Aşırı satış dili kullanma",
        ],
        "key_takeaways": [
            "Marka rengi #052562 korunmalı",
            "Montserrat tipografisi kullanılmalı",
            "Ton her zaman güven verici ve kurumsal olmalı",
        ],
        "confidence_score": 90,
        "status": "approved",
        "is_active": True,
        "reviewed_by_id": approver.id,
        "approved_by_id": approver.id,
        "reviewed_at": now,
        "approved_at": now,
        "approved_by_name": approver.full_name,
    }

    if profile is not None:
        for key, value in fields.items():
            setattr(profile, key, value)
        return profile, False

    profile = BrandIdentityProfile(id=uuid.uuid4(), brand_id=brand_id, agency_id=agency_id, **fields)
    session.add(profile)
    await session.flush()
    return profile, True


async def _get_or_create_subscription(session, agency_id) -> tuple[Subscription | None, bool]:
    plan_result = await session.execute(select(Plan).where(Plan.code == PlanCode.AGENCY_PLUS.value))
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        print(
            "[WARN] 'agency_plus' plan not found in `plans` table — run "
            "`python -m scripts.seed_plans` first. Skipping subscription."
        )
        return None, False

    result = await session.execute(
        select(Subscription).where(
            Subscription.agency_id == agency_id, Subscription.deleted_at.is_(None)
        )
    )
    sub = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if sub is not None:
        sub.plan_id = plan.id
        sub.status = SubscriptionStatus.ACTIVE.value
        return sub, False

    sub = Subscription(
        id=uuid.uuid4(), agency_id=agency_id, plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value, billing_provider="manual",
        current_period_start=now, current_period_end=now + timedelta(days=365),
    )
    session.add(sub)
    await session.flush()
    return sub, True


def _build_meta(cfg: dict) -> dict:
    meta = {
        "target_audience": cfg.get("audience"),
        "key_message": cfg.get("key_message"),
        "suggested_copy": cfg.get("suggested_copy"),
        "tone": cfg.get("tone"),
        "visual_direction": cfg.get("visual_direction"),
        "cta": cfg.get("cta"),
        "deliverable_format": cfg.get("dimensions"),
        "content_flow": cfg.get("content_flow"),
        "duration": cfg.get("duration"),
        "reference_notes": cfg.get("reference_notes"),
        "additional_notes": cfg.get("additional_notes"),
    }
    return {k: v for k, v in meta.items() if v is not None}


async def _get_or_create_brief(session, agency: Agency, brand: Brand, creator: User, cfg: dict) -> tuple[Brief, bool]:
    result = await session.execute(
        select(Brief).where(
            Brief.agency_id == agency.id, Brief.title == cfg["title"], Brief.deleted_at.is_(None)
        )
    )
    brief = result.scalar_one_or_none()
    if brief is not None:
        return brief, False

    description_parts = [cfg.get("purpose") or ""]
    brief = Brief(
        id=uuid.uuid4(),
        agency_id=agency.id,
        brand_id=brand.id,
        title=cfg["title"],
        description="\n\n".join(p for p in description_parts if p) or None,
        status=cfg["status"],
        priority=cfg["priority"],
        start_date=cfg["dates"]["start"],
        draft_date=cfg["dates"]["draft"],
        feedback_date=cfg["dates"]["feedback"],
        deadline=cfg["dates"]["deadline"],
        publish_date=cfg["dates"]["publish"],
        platforms=cfg["platforms"],
        content_types=cfg["content_types"],
        created_by_id=creator.id,
        source="agency",
        meta=_build_meta(cfg),
    )
    session.add(brief)
    await session.flush()
    return brief, True


def _build_demo_png() -> bytes:
    """A real, locally-generated 1080x1080 placeholder — no remote assets."""
    img = Image.new("RGB", (1080, 1080), color=(5, 37, 98))  # brand navy #052562
    accent = Image.new("RGB", (1080, 200), color=(15, 181, 174))  # controlled turquoise
    img.paste(accent, (0, 880))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _create_demo_deliverable(
    session, brief: Brief, agency_id, brand_id, designer: User, brand_user: User
) -> None:
    """Deliverable + real local asset + 2 open / 1 resolved annotation (with agency
    and brand replies on the resolved one) — only called for a freshly-created brief."""
    deliverable = Deliverable(
        id=uuid.uuid4(),
        agency_id=agency_id,
        brand_id=brand_id,
        brief_id=brief.id,
        title="İşletmenizin Zamanı Değerli — Video Kapak Görseli",
        description="Reels / LinkedIn video için kapak karesi ve stil referansı.",
        deliverable_type="image",
        status="revision_requested",
        version_number=1,
        revision_count=1,
        revision_note="Marka; başlık kontrastı ve logo güvenli alanı için revizyon istedi.",
        submitted_by_id=designer.id,
        submitted_at=datetime.now(UTC),
    )
    session.add(deliverable)
    await session.flush()

    png_bytes = _build_demo_png()
    safe_name = normalize_filename("ulusal-faktoring-video-kapak.png")
    storage_key = f"{agency_id}/deliverables/{safe_name}"
    storage = get_storage_backend()
    await storage.save(png_bytes, storage_key)

    asset = Asset(
        id=uuid.uuid4(),
        agency_id=agency_id,
        brand_id=brand_id,
        uploaded_by_id=designer.id,
        filename=safe_name,
        original_filename="ulusal-faktoring-video-kapak.png",
        mime_type="image/png",
        size_bytes=len(png_bytes),
        storage_provider="local",
        storage_key=storage_key,
        checksum=hashlib.sha256(png_bytes).hexdigest(),
        visibility="client_visible",
    )
    session.add(asset)
    await session.flush()

    session.add(AssetLink(id=uuid.uuid4(), asset_id=asset.id, brief_id=brief.id, deliverable_id=deliverable.id))

    annotations = [
        {
            "x": 52.0, "y": 18.0, "body": "Başlık alanı mobil görünümde biraz daha güçlü olabilir.",
            "status": "open",
        },
        {
            "x": 30.0, "y": 72.0, "body": "Alt açıklamanın kontrastını artırabilir miyiz?",
            "status": "open",
        },
        {
            "x": 82.0, "y": 88.0, "body": "Logo çevresindeki güvenli alan uygun, bu nokta çözüldü.",
            "status": "resolved",
        },
    ]
    now = datetime.now(UTC)
    for i, a in enumerate(annotations, start=1):
        ann = DeliverableAnnotation(
            id=uuid.uuid4(),
            agency_id=agency_id,
            brand_id=brand_id,
            brief_id=brief.id,
            deliverable_id=deliverable.id,
            asset_id=asset.id,
            version_number=1,
            x_percent=a["x"],
            y_percent=a["y"],
            label_number=i,
            status=a["status"],
            annotation_type="revision",
            visibility="client_visible",
            body=a["body"],
            created_by_id=brand_user.id,
            resolved_by_id=designer.id if a["status"] == "resolved" else None,
            resolved_at=now if a["status"] == "resolved" else None,
        )
        session.add(ann)
        await session.flush()

        if a["status"] == "resolved":
            session.add(AnnotationReply(
                id=uuid.uuid4(), annotation_id=ann.id, author_user_id=designer.id,
                author_name=designer.full_name,
                body="Kontrastı ve güvenli alanı güncelledik, tekrar kontrol edebilir misiniz?",
                visibility="client_visible",
            ))
            session.add(AnnotationReply(
                id=uuid.uuid4(), annotation_id=ann.id, author_user_id=brand_user.id,
                author_name=brand_user.full_name,
                body="Teşekkürler, bu nokta artık uygun görünüyor.",
                visibility="client_visible",
            ))


async def _get_or_create_approval(session, brief: Brief, requested_by: User, brand_user: User, brief_status: str) -> bool:
    target_status = _APPROVAL_STATUS_FOR_BRIEF_STATUS.get(brief_status)
    if target_status is None:
        return False

    result = await session.execute(
        select(Approval).where(Approval.brief_id == brief.id, Approval.deleted_at.is_(None))
    )
    if result.scalar_one_or_none() is not None:
        return False

    decided = target_status != ApprovalStatus.PENDING.value
    now = datetime.now(UTC)
    session.add(Approval(
        id=uuid.uuid4(),
        brief_id=brief.id,
        status=target_status,
        channel="internal",
        requested_by_id=requested_by.id,
        assigned_to_user_id=brand_user.id,
        decided_by_user_id=brand_user.id if decided else None,
        decided_at=now if decided else None,
        approved_by_name=brand_user.full_name if decided else None,
    ))
    return True


# ── Main orchestration ────────────────────────────────────────────────────────

async def seed_ulusal_demo() -> None:
    _assert_safe_environment()

    counts = {
        "agency_created": False, "brand_created": False, "identity_created": False,
        "subscription_created": False, "users_created": 0, "users_updated": 0,
        "agency_members_created": 0, "brand_members_created": 0,
        "briefs_created": 0, "briefs_skipped": 0, "assignees_created": 0,
        "approvals_created": 0, "deliverable_created": False,
    }

    async with AsyncSessionLocal() as session:
        try:
            agency, agency_created = await _get_or_create_agency(session)
            counts["agency_created"] = agency_created

            agency_user_by_email: dict[str, User] = {}
            for ud in AGENCY_USERS:
                user, created = await _get_or_create_user(
                    session, ud["email"], ud["full_name"], UserType.AGENCY_USER.value
                )
                counts["users_created" if created else "users_updated"] += 1
                _, member_created = await _get_or_create_agency_member(
                    session, agency.id, user.id, ud["agency_role"]
                )
                if member_created:
                    counts["agency_members_created"] += 1
                agency_user_by_email[ud["email"]] = user

            efe = agency_user_by_email["efe@360stradigi.com"]

            brand, brand_created = await _get_or_create_brand(session, agency.id)
            counts["brand_created"] = brand_created

            brand_user, brand_user_created = await _get_or_create_user(
                session, BRAND_USER["email"], BRAND_USER["full_name"], UserType.BRAND_USER.value
            )
            counts["users_created" if brand_user_created else "users_updated"] += 1
            _, brand_member_created = await _get_or_create_brand_member(
                session, brand.id, brand_user.id, BRAND_USER["brand_role"]
            )
            if brand_member_created:
                counts["brand_members_created"] += 1

            _, identity_created = await _get_or_create_brand_identity(session, brand.id, agency.id, efe)
            counts["identity_created"] = identity_created

            _, sub_created = await _get_or_create_subscription(session, agency.id)
            counts["subscription_created"] = sub_created

            for cfg in BRIEFS:
                brief, brief_created = await _get_or_create_brief(session, agency, brand, efe, cfg)
                if not brief_created:
                    counts["briefs_skipped"] += 1
                    continue
                counts["briefs_created"] += 1

                assignee = agency_user_by_email[cfg["assignee_email"]]
                caps = default_caps_for_role(cfg["participant_role"])
                session.add(BriefAssignee(
                    id=uuid.uuid4(), brief_id=brief.id, user_id=assignee.id,
                    role_label=assignee.full_name, participant_role=cfg["participant_role"],
                    **caps,
                ))
                counts["assignees_created"] += 1

                if await _get_or_create_approval(session, brief, efe, brand_user, cfg["status"]):
                    counts["approvals_created"] += 1

                if cfg.get("has_demo_deliverable"):
                    await _create_demo_deliverable(
                        session, brief, agency.id, brand.id, assignee, brand_user
                    )
                    counts["deliverable_created"] = True

            await session.commit()
        except Exception:
            await session.rollback()
            raise

    print("[OK] Ulusal Faktoring demo seed complete.")
    for key, value in counts.items():
        print(f"     {key}: {value}")


if __name__ == "__main__":
    asyncio.run(seed_ulusal_demo())

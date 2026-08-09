"""Seed VEXX demo data for brand portal testing.

Creates realistic briefs, calendar items, and reports for the VEXX brand
so the brand portal shows meaningful data instead of empty states.

Usage (from repo root, with docker DB running):
    python scripts/seed_vexx_brand_portal.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from datetime import date as date_class

_backend = os.path.join(os.path.dirname(__file__), "..", "apps", "backend")
if os.path.isdir(_backend):
    sys.path.insert(0, os.path.abspath(_backend))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.agency import Agency  # noqa: E402
from app.models.brand import Brand  # noqa: E402
from app.models.brief import Brief  # noqa: E402
from app.models.calendar import CalendarItem  # noqa: E402
from app.models.report import Report  # noqa: E402
from app.models.user import User  # noqa: E402

BRIEF_SEEDS = [
    ("VEXX Q3 Instagram Kampanyasi", "in_review", "high", "2026-08-15"),
    ("Yaz Sezonu Sosyal Medya Brifingi", "approved", "normal", "2026-07-31"),
    ("TikTok Influencer Isbirligi Plani", "revision_requested", "urgent", "2026-07-20"),
    ("Brand Identity Guncelleme", "draft", "normal", "2026-09-01"),
    ("Eylul Kampanya Brifingi", "draft", "low", "2026-09-15"),
]

CALENDAR_SEEDS = [
    ("VEXX Instagram Story - Yaz Koleksiyonu", "instagram", "story", "waiting_approval",
     datetime.now(UTC) + timedelta(days=3)),
    ("TikTok Trend Video", "tiktok", "reels", "in_design",
     datetime.now(UTC) + timedelta(days=5)),
    ("LinkedIn Marka Tanıtımı", "linkedin", "post", "planned",
     datetime.now(UTC) + timedelta(days=8)),
    ("Instagram Post - Kampanya", "instagram", "post", "approved",
     datetime.now(UTC) + timedelta(days=10)),
    ("Facebook Etkinlik Duyurusu", "facebook", "post", "planned",
     datetime.now(UTC) + timedelta(days=14)),
    ("YouTube Shorts", "youtube", "video", "planned",
     datetime.now(UTC) + timedelta(days=21)),
]

REPORT_SEEDS = [
    ("VEXX Haziran 2026 Marka Raporu", "monthly_brand", "generated",
     "2026-06-01", "2026-06-30"),
    ("VEXX Mayis 2026 Marka Raporu", "monthly_brand", "generated",
     "2026-05-01", "2026-05-31"),
    ("Q2 2026 Kampanya Ozeti", "campaign_summary", "shared",
     "2026-04-01", "2026-06-30"),
]


async def run() -> None:
    async with AsyncSessionLocal() as db:
        # Find VEXX brand
        result = await db.execute(
            select(Brand).where(Brand.name == "VEXX", Brand.deleted_at.is_(None))
        )
        brand = result.scalar_one_or_none()
        if brand is None:
            print("[!] VEXX markasi bulunamadi. Once create_brand_user.py calistirin.")
            return
        print(f"[=] Marka: {brand.name} ({brand.id})")

        # Find agency
        if brand.agency_id is None:
            print("[!] Markanin ajans baglantisi yok.")
            return

        agency_result = await db.execute(
            select(Agency).where(Agency.id == brand.agency_id, Agency.deleted_at.is_(None))
        )
        agency = agency_result.scalar_one_or_none()
        if agency is None:
            print("[!] Ajans bulunamadi.")
            return
        print(f"[=] Ajans: {agency.name} ({agency.id})")

        # Find a user to set as creator (any user in DB)
        user_result = await db.execute(select(User).where(User.deleted_at.is_(None)).limit(1))
        creator = user_result.scalar_one_or_none()
        if creator is None:
            print("[!] Hicbir kullanici bulunamadi.")
            return

        # Seed briefs
        brief_count = 0
        for title, status, priority, deadline in BRIEF_SEEDS:
            existing = await db.execute(
                select(Brief).where(Brief.title == title, Brief.brand_id == brand.id)
            )
            if existing.scalar_one_or_none() is not None:
                print(f"[=] Brief zaten var: {title}")
                continue
            brief = Brief(
                agency_id=agency.id,
                brand_id=brand.id,
                title=title,
                description=(
                    f"{title} icin detayli brief aciklamasi. "
                    "Marka kimligine uygun icerik uretilmeli."
                ),
                status=status,
                priority=priority,
                deadline=deadline,
                created_by_id=creator.id,
            )
            db.add(brief)
            brief_count += 1
            print(f"[+] Brief: {title} ({status})")

        # Seed calendar items
        cal_count = 0
        for title, platform, item_type, status, publish_at in CALENDAR_SEEDS:
            existing = await db.execute(
                select(CalendarItem).where(
                    CalendarItem.title == title,
                    CalendarItem.brand_id == brand.id
                )
            )
            if existing.scalar_one_or_none() is not None:
                print(f"[=] Takvim ogesi zaten var: {title}")
                continue
            item = CalendarItem(
                agency_id=agency.id,
                brand_id=brand.id,
                title=title,
                item_type=item_type,
                platform=platform,
                status=status,
                publish_at=publish_at,
                created_by_id=creator.id,
            )
            db.add(item)
            cal_count += 1
            print(f"[+] Takvim: {title} ({platform} / {status})")

        # Seed reports
        rep_count = 0
        for title, report_type, status, period_start, period_end in REPORT_SEEDS:
            existing = await db.execute(
                select(Report).where(Report.title == title, Report.brand_id == brand.id)
            )
            if existing.scalar_one_or_none() is not None:
                print(f"[=] Rapor zaten var: {title}")
                continue
            report = Report(
                agency_id=agency.id,
                brand_id=brand.id,
                title=title,
                report_type=report_type,
                status=status,
                period_start=date_class.fromisoformat(period_start),
                period_end=date_class.fromisoformat(period_end),
                created_by_id=creator.id,
            )
            db.add(report)
            rep_count += 1
            print(f"[+] Rapor: {title}")

        await db.commit()
        print()
        print("-" * 55)
        print(f"  Eklenen briefler    : {brief_count}")
        print(f"  Eklenen takvim      : {cal_count}")
        print(f"  Eklenen raporlar    : {rep_count}")
        print("-" * 55)
        print("Seed tamamlandi.")


if __name__ == "__main__":
    db_hint = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "..."
    print(f"Veritabani: {db_hint}")
    print()
    asyncio.run(run())

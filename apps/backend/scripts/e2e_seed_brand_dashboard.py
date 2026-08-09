"""E2E fixture for e2e/brand-dashboard.spec.ts.

Creates one Agency + agency owner User, one Brand + brand owner User, and a
spread of Briefs across statuses so the redesigned /brand/dashboard has real
content to assert against:
  - 5 "ready_for_review" briefs (actionable -> tests the >4 action-queue cap
    and the "Tum N aksiyonu gor" link)
  - 1 legacy "in_review" (non brand_portal source) brief with a past deadline
    (actionable AND overdue)
  - 1 "revision_requested" brief (NOT actionable -- agency's turn, must not
    appear in the action queue)
  - 1 "approved" and 1 "draft" brief (KPI sub-metrics, Son Briefler list)
One brief's deadline falls this week (drives a "Bu Hafta" calendar entry via
the existing brief-milestone calendar service, no new backend code needed).
Two Notification rows are inserted directly (bypassing the async event
pipeline) with a real action_url pointing at a seeded brief, for the "Son
Hareketler" deep-link assertions.

Two modes:
  python e2e_seed_brand_dashboard.py seed             -> prints E2E_* env vars
  python e2e_seed_brand_dashboard.py cleanup <agency_id>
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.agency import Agency  # noqa: E402
from app.models.agency_member import AgencyMember  # noqa: E402
from app.models.brand import Brand  # noqa: E402
from app.models.brand_member import BrandMember  # noqa: E402
from app.models.brief import Brief  # noqa: E402
from app.models.enums import (  # noqa: E402
    AgencyMemberRole,
    AgencyMemberStatus,
    AgencyStatus,
    BrandMemberRole,
    BrandMemberStatus,
    BrandStatus,
    UserType,
)
from app.models.notification import Notification, NotificationEvent  # noqa: E402
from app.models.user import User  # noqa: E402

AGENCY_EMAIL = "flobrief-e2e-dashboard-agency@example.com"
BRAND_EMAIL = "flobrief-e2e-dashboard-brand@example.com"
PASSWORD = "E2eTest1234!"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _assert_local_test_database() -> None:
    host = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing to run: DATABASE_URL host {host!r} is not local {_LOCAL_HOSTS}."
        )
    if settings.is_production:
        raise RuntimeError("Refusing to run: APP_ENV=production.")


async def cleanup_by_email() -> None:
    async with AsyncSessionLocal() as db:
        for email in (AGENCY_EMAIL, BRAND_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                continue
            member = (await db.execute(
                select(AgencyMember).where(AgencyMember.user_id == user.id)
            )).scalar_one_or_none()
            if member is not None:
                agency = await db.get(Agency, member.agency_id)
                if agency is not None:
                    await db.delete(agency)
                brands = (await db.execute(
                    select(Brand).where(Brand.agency_id == member.agency_id)
                )).scalars().all()
                for brand in brands:
                    await db.delete(brand)
        await db.commit()

        for email in (AGENCY_EMAIL, BRAND_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


async def cleanup_by_agency_id(agency_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        agency = await db.get(Agency, agency_id)
        if agency is not None:
            await db.delete(agency)
        brands = (await db.execute(select(Brand).where(Brand.agency_id == agency_id))).scalars().all()
        for brand in brands:
            await db.delete(brand)
        await db.commit()

        for email in (AGENCY_EMAIL, BRAND_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


async def seed() -> dict[str, str]:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        agency = Agency(
            id=uuid.uuid4(), name="E2E Dashboard Agency",
            slug=f"e2e-dashboard-agency-{uuid.uuid4().hex[:8]}", status=AgencyStatus.ACTIVE.value,
        )
        brand = Brand(
            id=uuid.uuid4(), agency_id=agency.id, name="E2E Dashboard Brand",
            slug=f"e2e-dashboard-brand-{uuid.uuid4().hex[:8]}", status=BrandStatus.ACTIVE.value,
        )
        db.add_all([agency, brand])

        agency_user = User(
            id=uuid.uuid4(), email=AGENCY_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="E2E Dashboard Agency Owner", user_type=UserType.AGENCY_USER.value,
            is_active=True, is_verified=True,
        )
        brand_user = User(
            id=uuid.uuid4(), email=BRAND_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="E2E Dashboard Brand Owner", user_type=UserType.BRAND_USER.value,
            is_active=True, is_verified=True,
        )
        db.add_all([agency_user, brand_user])
        await db.flush()

        db.add_all([
            AgencyMember(
                id=uuid.uuid4(), agency_id=agency.id, user_id=agency_user.id,
                role=AgencyMemberRole.OWNER.value, status=AgencyMemberStatus.ACTIVE.value,
            ),
            BrandMember(
                id=uuid.uuid4(), brand_id=brand.id, user_id=brand_user.id,
                role=BrandMemberRole.BRAND_OWNER.value, status=BrandMemberStatus.ACTIVE.value,
            ),
        ])

        briefs: list[Brief] = []
        for i in range(5):
            briefs.append(Brief(
                id=uuid.uuid4(), agency_id=agency.id, brand_id=brand.id,
                title=f"E2E Onay Bekleyen Brief {i + 1}", status="ready_for_review",
                source="brand_portal", deadline=(now + timedelta(days=3 + i)).date().isoformat(),
                created_by_id=agency_user.id,
            ))

        this_week_brief = Brief(
            id=uuid.uuid4(), agency_id=agency.id, brand_id=brand.id,
            title="E2E Bu Hafta Teslim Brief", status="ready_for_review",
            source="brand_portal", deadline=(now + timedelta(days=1)).date().isoformat(),
            created_by_id=agency_user.id,
        )
        overdue_legacy_brief = Brief(
            id=uuid.uuid4(), agency_id=agency.id, brand_id=brand.id,
            title="E2E Gecikmis Legacy Brief", status="in_review",
            source=None, deadline=(now - timedelta(days=2)).date().isoformat(),
            created_by_id=agency_user.id,
        )
        revision_brief = Brief(
            id=uuid.uuid4(), agency_id=agency.id, brand_id=brand.id,
            title="E2E Revizyon Istenen Brief", status="revision_requested",
            source="brand_portal", created_by_id=agency_user.id,
        )
        approved_brief = Brief(
            id=uuid.uuid4(), agency_id=agency.id, brand_id=brand.id,
            title="E2E Onaylanan Brief", status="approved",
            source="brand_portal", created_by_id=agency_user.id,
        )
        draft_brief = Brief(
            id=uuid.uuid4(), agency_id=agency.id, brand_id=brand.id,
            title="E2E Taslak Brief", status="draft",
            source="brand_portal", created_by_id=agency_user.id,
        )

        all_briefs = [*briefs, this_week_brief, overdue_legacy_brief, revision_brief, approved_brief, draft_brief]
        db.add_all(all_briefs)
        await db.flush()

        event = NotificationEvent(
            id=uuid.uuid4(), event_type="brief.approved", agency_id=agency.id, brand_id=brand.id,
            actor_user_id=agency_user.id, payload={"brief_id": str(approved_brief.id)},
            processed_at=now,
        )
        db.add(event)
        await db.flush()

        db.add(Notification(
            id=uuid.uuid4(), user_id=brand_user.id, agency_id=agency.id, brand_id=brand.id,
            event_id=event.id, title="Brief onaylandi",
            body=f'"{approved_brief.title}" onaylandi.', event_type="brief.approved",
            is_read=False,
        ))

        await db.commit()

        return {
            "agency_id": str(agency.id),
            "action_brief_id": str(briefs[0].id),
            "approved_brief_id": str(approved_brief.id),
        }


async def main() -> None:
    _assert_local_test_database()

    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if mode == "cleanup":
        if len(sys.argv) > 2:
            await cleanup_by_agency_id(uuid.UUID(sys.argv[2]))
        else:
            await cleanup_by_email()
        print("cleaned up")
        return

    await cleanup_by_email()
    ids = await seed()
    print("E2E_BRAND_EMAIL=" + BRAND_EMAIL)
    print("E2E_PASSWORD=" + PASSWORD)
    print("E2E_ACTION_BRIEF_ID=" + ids["action_brief_id"])
    print("E2E_APPROVED_BRIEF_ID=" + ids["approved_brief_id"])
    print("__AGENCY_ID__=" + ids["agency_id"])


if __name__ == "__main__":
    asyncio.run(main())

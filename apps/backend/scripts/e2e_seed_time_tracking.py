"""E2E fixture for e2e/time-tracking-flow.spec.ts.

Creates one Agency with a Brand + Brief, and two AgencyMembers:
  - a manager (role=owner) who has TIME_ENTRY_VIEW_TEAM and can see the
    team timesheet / brand / brief reports
  - a designer (role=designer) who has TIME_ENTRY_LOG only and must be
    refused (real 403, not just a hidden tab) when hitting any team-scoped
    time-report endpoint

No TimeEntry rows are pre-seeded here — the spec itself creates every timer
start/stop and manual entry through the real browser UI, so every duration
asserted in the spec comes from a row the test actually created.

Two modes:
  python e2e_seed_time_tracking.py seed      -> prints E2E_* env vars
  python e2e_seed_time_tracking.py cleanup <agency_id>  -> deletes the fixture

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production" — mirrors e2e_seed_brief_workspace.py.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
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
from app.models.brief import Brief  # noqa: E402
from app.models.enums import (  # noqa: E402
    AgencyMemberRole,
    AgencyMemberStatus,
    AgencyStatus,
    BrandStatus,
    UserType,
)
from app.models.user import User  # noqa: E402

MANAGER_EMAIL = "flobrief-e2e-time-manager@example.com"
DESIGNER_EMAIL = "flobrief-e2e-time-designer@example.com"
PASSWORD = "E2eTest1234!"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _assert_local_test_database() -> None:
    host = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing to run: DATABASE_URL host {host!r} is not a local host {_LOCAL_HOSTS}."
        )
    if settings.is_production:
        raise RuntimeError("Refusing to run: APP_ENV=production.")


async def cleanup_by_email() -> None:
    async with AsyncSessionLocal() as db:
        for email in (MANAGER_EMAIL, DESIGNER_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                continue
            member = (
                await db.execute(select(AgencyMember).where(AgencyMember.user_id == user.id))
            ).scalar_one_or_none()
            if member is not None:
                agency = await db.get(Agency, member.agency_id)
                if agency is not None:
                    await db.delete(agency)
                brands = (
                    (await db.execute(select(Brand).where(Brand.agency_id == member.agency_id)))
                    .scalars()
                    .all()
                )
                for brand in brands:
                    await db.delete(brand)
        await db.commit()

        for email in (MANAGER_EMAIL, DESIGNER_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


async def cleanup_by_agency_id(agency_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        agency = await db.get(Agency, agency_id)
        if agency is not None:
            await db.delete(agency)  # cascades agency_members/briefs/time_entries/...
        brands = (
            (await db.execute(select(Brand).where(Brand.agency_id == agency_id))).scalars().all()
        )
        for brand in brands:
            await db.delete(brand)
        await db.commit()

        for email in (MANAGER_EMAIL, DESIGNER_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


async def seed_db() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as db:
        agency = Agency(
            id=uuid.uuid4(),
            name="E2E Time Tracking Agency",
            slug=f"e2e-time-agency-{uuid.uuid4().hex[:8]}",
            status=AgencyStatus.ACTIVE.value,
        )
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name="E2E Time Tracking Brand",
            slug=f"e2e-time-brand-{uuid.uuid4().hex[:8]}",
            status=BrandStatus.ACTIVE.value,
        )
        db.add_all([agency, brand])

        manager = User(
            id=uuid.uuid4(),
            email=MANAGER_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Time Manager",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        designer = User(
            id=uuid.uuid4(),
            email=DESIGNER_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Time Designer",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        db.add_all([manager, designer])
        await db.flush()

        db.add_all(
            [
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=manager.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=designer.id,
                    role=AgencyMemberRole.DESIGNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
            ]
        )

        brief = Brief(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand.id,
            title="E2E Time Tracking Brief",
            status="in_production",
            created_by_id=manager.id,
            estimated_hours=40.0,
        )
        db.add(brief)
        await db.commit()

        return agency.id, brand.id, brief.id


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
    agency_id, brand_id, brief_id = await seed_db()
    print("E2E_MANAGER_EMAIL=" + MANAGER_EMAIL)
    print("E2E_DESIGNER_EMAIL=" + DESIGNER_EMAIL)
    print("E2E_PASSWORD=" + PASSWORD)
    print("E2E_BRIEF_ID=" + str(brief_id))
    print("E2E_BRAND_ID=" + str(brand_id))
    print("__AGENCY_ID__=" + str(agency_id))


if __name__ == "__main__":
    asyncio.run(main())

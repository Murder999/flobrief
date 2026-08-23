"""E2E fixture for e2e/capacity-planning-flow.spec.ts.

Creates one Agency with a Brand + one unassigned Brief (estimated_hours set,
zero BriefAssignee rows -> a real "unassigned work" item derived at
read-time by CapacityCalculationService.unassigned_work(), not a hardcoded
flag), and two real AgencyMembers each with a pre-seeded WorkSchedule:
  - an owner (role=owner) with CAPACITY_MANAGE_SCHEDULE/ALLOCATION,
    TIME_OFF_APPROVE, CAPACITY_VIEW_TEAM
  - a designer (role=designer) with CAPACITY_VIEW_OWN + TIME_OFF_REQUEST
    only, used to prove "only sees own capacity" is a real 403, not just a
    hidden tab

Both WorkSchedules are seeded uniformly across all 7 weekdays (480 minutes,
is_working_day=True) rather than the usual Mon-Fri pattern specifically so
capacity math in the spec is deterministic regardless of which real weekday
the suite happens to run on (a Sat/Sun run would otherwise see 0-capacity
days and break the "8.0s per day" / "56.0s per week" assertions).

No TimeOff/CapacityException/WorkAllocation rows are pre-seeded -- the spec
itself creates a time-off request+approval and a manual allocation through
the real browser UI, so every capacity number asserted comes from a row the
test actually created.

Two modes:
  python e2e_seed_capacity.py seed            -> prints E2E_* env vars
  python e2e_seed_capacity.py cleanup <agency_id>

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production" -- mirrors e2e_seed_time_tracking.py.
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
from app.models.work_schedule import WorkSchedule, WorkScheduleDay  # noqa: E402

OWNER_EMAIL = "flobrief-e2e-capacity-owner@example.com"
DESIGNER_EMAIL = "flobrief-e2e-capacity-designer@example.com"
PASSWORD = "E2eTest1234!"
DAILY_CAPACITY_MINUTES = 480

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
        for email in (OWNER_EMAIL, DESIGNER_EMAIL):
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

        for email in (OWNER_EMAIL, DESIGNER_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


async def cleanup_by_agency_id(agency_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        agency = await db.get(Agency, agency_id)
        if agency is not None:
            await db.delete(agency)  # cascades agency_members/briefs/work_schedules/...
        brands = (
            (await db.execute(select(Brand).where(Brand.agency_id == agency_id))).scalars().all()
        )
        for brand in brands:
            await db.delete(brand)
        await db.commit()

        for email in (OWNER_EMAIL, DESIGNER_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


def _uniform_week(schedule_id: uuid.UUID) -> list[WorkScheduleDay]:
    return [
        WorkScheduleDay(
            id=uuid.uuid4(),
            work_schedule_id=schedule_id,
            weekday=weekday,
            is_working_day=True,
            capacity_minutes=DAILY_CAPACITY_MINUTES,
        )
        for weekday in range(7)
    ]


async def seed_db() -> dict[str, uuid.UUID]:
    async with AsyncSessionLocal() as db:
        agency = Agency(
            id=uuid.uuid4(),
            name="E2E Capacity Agency",
            slug=f"e2e-capacity-agency-{uuid.uuid4().hex[:8]}",
            status=AgencyStatus.ACTIVE.value,
        )
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name="E2E Capacity Brand",
            slug=f"e2e-capacity-brand-{uuid.uuid4().hex[:8]}",
            status=BrandStatus.ACTIVE.value,
        )
        db.add_all([agency, brand])

        owner = User(
            id=uuid.uuid4(),
            email=OWNER_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Capacity Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        designer = User(
            id=uuid.uuid4(),
            email=DESIGNER_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Capacity Designer",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        db.add_all([owner, designer])
        await db.flush()

        db.add_all(
            [
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=owner.id,
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

        owner_schedule = WorkSchedule(
            id=uuid.uuid4(),
            agency_id=agency.id,
            user_id=owner.id,
            timezone="Europe/Istanbul",
        )
        designer_schedule = WorkSchedule(
            id=uuid.uuid4(),
            agency_id=agency.id,
            user_id=designer.id,
            timezone="Europe/Istanbul",
        )
        db.add_all([owner_schedule, designer_schedule])
        await db.flush()
        db.add_all(_uniform_week(owner_schedule.id) + _uniform_week(designer_schedule.id))

        unassigned_brief = Brief(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand.id,
            title="E2E Unassigned Capacity Brief",
            status="in_production",
            created_by_id=owner.id,
            estimated_hours=8.0,
        )
        db.add(unassigned_brief)
        await db.commit()

        return {
            "agency_id": agency.id,
            "brand_id": brand.id,
            "owner_id": owner.id,
            "designer_id": designer.id,
            "brief_id": unassigned_brief.id,
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
    ids = await seed_db()
    print("E2E_OWNER_EMAIL=" + OWNER_EMAIL)
    print("E2E_DESIGNER_EMAIL=" + DESIGNER_EMAIL)
    print("E2E_PASSWORD=" + PASSWORD)
    print("E2E_OWNER_ID=" + str(ids["owner_id"]))
    print("E2E_DESIGNER_ID=" + str(ids["designer_id"]))
    print("E2E_BRIEF_ID=" + str(ids["brief_id"]))
    print("E2E_BRAND_ID=" + str(ids["brand_id"]))
    print("__AGENCY_ID__=" + str(ids["agency_id"]))


if __name__ == "__main__":
    asyncio.run(main())

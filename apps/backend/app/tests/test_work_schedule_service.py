"""WorkScheduleService tests: one-active-schedule-per-user enforcement via
soft-delete-old+insert-new (never an in-place mutation), IANA timezone
validation, and tenant isolation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.models.work_schedule import WorkSchedule
from app.schemas.work_schedule import WorkScheduleCreate, WorkScheduleDayCreate
from app.services.work_schedule_service import WorkScheduleService

_FULL_WEEK_MON_FRI = [
    WorkScheduleDayCreate(weekday=d, is_working_day=d < 5, capacity_minutes=480 if d < 5 else 0)
    for d in range(7)
]


async def _create_agency_with_user(label: str) -> tuple[uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        agency = Agency(
            id=uuid.uuid4(),
            name=f"{label} Agency",
            slug=f"{label.lower()}-agency-{suffix}",
        )
        session.add(agency)
        await session.flush()

        user = User(
            id=uuid.uuid4(),
            email=f"{label.lower()}-{suffix}@test.local",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name=f"Test {label}",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        session.add(
            AgencyMember(
                id=uuid.uuid4(),
                agency_id=agency.id,
                user_id=user.id,
                role=AgencyMemberRole.ADMIN.value,
                status=AgencyMemberStatus.ACTIVE.value,
            )
        )
        await session.commit()
        return agency.id, user.id


async def test_upsert_creates_schedule_with_all_seven_days() -> None:
    agency_id, user_id = await _create_agency_with_user("WSCreate")
    async with AsyncSessionLocal() as session:
        schedule, days = await WorkScheduleService(session).upsert(
            agency_id,
            WorkScheduleCreate(
                user_id=user_id, timezone="Europe/Istanbul", days=_FULL_WEEK_MON_FRI
            ),
        )

    assert schedule.agency_id == agency_id
    assert schedule.user_id == user_id
    assert schedule.timezone == "Europe/Istanbul"
    assert len(days) == 7
    assert sum(d.capacity_minutes for d in days) == 5 * 480


async def test_upsert_replaces_prior_schedule_and_soft_deletes_old() -> None:
    agency_id, user_id = await _create_agency_with_user("WSReplace")
    async with AsyncSessionLocal() as session:
        svc = WorkScheduleService(session)
        first, _ = await svc.upsert(
            agency_id, WorkScheduleCreate(user_id=user_id, days=_FULL_WEEK_MON_FRI)
        )
        second, second_days = await svc.upsert(
            agency_id,
            WorkScheduleCreate(
                user_id=user_id,
                timezone="America/New_York",
                days=[
                    WorkScheduleDayCreate(weekday=d, is_working_day=True, capacity_minutes=360)
                    for d in range(7)
                ],
            ),
        )

    assert second.id != first.id
    assert second.timezone == "America/New_York"
    assert all(d.capacity_minutes == 360 for d in second_days)

    async with AsyncSessionLocal() as session:
        active = await WorkScheduleService(session).get_active(agency_id, user_id)
    assert active is not None
    active_schedule, active_days = active
    assert active_schedule.id == second.id
    assert len(active_days) == 7

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(WorkSchedule).where(WorkSchedule.id == first.id))
        old_row = result.scalar_one()
    assert old_row.deleted_at is not None, "the superseded schedule must be soft-deleted"


async def test_only_one_active_schedule_survives_repeated_upserts() -> None:
    agency_id, user_id = await _create_agency_with_user("WSSingleActive")
    async with AsyncSessionLocal() as session:
        svc = WorkScheduleService(session)
        for _ in range(3):
            await svc.upsert(
                agency_id, WorkScheduleCreate(user_id=user_id, days=_FULL_WEEK_MON_FRI)
            )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WorkSchedule).where(
                WorkSchedule.agency_id == agency_id,
                WorkSchedule.user_id == user_id,
                WorkSchedule.deleted_at.is_(None),
            )
        )
        active_rows = result.scalars().all()
    assert len(active_rows) == 1


def test_invalid_iana_timezone_is_rejected_by_schema() -> None:
    with pytest.raises(ValueError):
        WorkScheduleCreate(user_id=uuid.uuid4(), timezone="Not/AZone", days=_FULL_WEEK_MON_FRI)


def test_valid_iana_timezone_is_accepted() -> None:
    schedule = WorkScheduleCreate(
        user_id=uuid.uuid4(), timezone="Asia/Tokyo", days=_FULL_WEEK_MON_FRI
    )
    assert schedule.timezone == "Asia/Tokyo"


def test_duplicate_weekday_in_days_is_rejected() -> None:
    with pytest.raises(ValueError):
        WorkScheduleCreate(
            user_id=uuid.uuid4(),
            days=[
                WorkScheduleDayCreate(weekday=0, capacity_minutes=480),
                WorkScheduleDayCreate(weekday=0, capacity_minutes=240),
            ],
        )


async def test_schedule_is_tenant_isolated() -> None:
    agency_a, user_a = await _create_agency_with_user("WSTenantA")
    agency_b, _ = await _create_agency_with_user("WSTenantB")

    async with AsyncSessionLocal() as session:
        await WorkScheduleService(session).upsert(
            agency_a, WorkScheduleCreate(user_id=user_a, days=_FULL_WEEK_MON_FRI)
        )

    async with AsyncSessionLocal() as session:
        # agency B's tenant scope must never surface agency A's schedule,
        # even when queried by the correct user_id.
        cross_tenant_read = await WorkScheduleService(session).get_active(agency_b, user_a)
    assert cross_tenant_read is None

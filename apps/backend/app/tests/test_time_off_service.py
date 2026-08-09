"""TimeOffService tests: request/approve/reject flow, and the all-day
UTC-boundary math — a full-day leave must round-trip back to the same local
calendar day it was requested for, regardless of which IANA timezone reads
it back, and regardless of the WorkSchedule timezone driving the write."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.schemas.time_off import TimeOffCreate, TimeOffReject
from app.schemas.work_schedule import WorkScheduleCreate, WorkScheduleDayCreate
from app.services.time_off_service import TimeOffService, compute_all_day_utc_bounds
from app.services.work_schedule_service import WorkScheduleService


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


# ── Pure boundary math (no DB) ───────────────────────────────────────────────


def test_all_day_single_day_bounds_in_istanbul() -> None:
    day = datetime(2026, 3, 10, tzinfo=UTC)
    start_utc, end_utc = compute_all_day_utc_bounds(day, day, "Europe/Istanbul")

    tz = ZoneInfo("Europe/Istanbul")
    assert start_utc.astimezone(tz).date().isoformat() == "2026-03-10"
    assert start_utc.astimezone(tz).time().isoformat() == "00:00:00"
    assert end_utc.astimezone(tz).date().isoformat() == "2026-03-11"
    assert end_utc.astimezone(tz).time().isoformat() == "00:00:00"
    assert (end_utc - start_utc) == timedelta(days=1)


def test_all_day_bounds_do_not_shift_the_calendar_day_in_a_far_timezone() -> None:
    """The core guarantee: a request framed in America/Los_Angeles local time
    must still land on the *same* local calendar day when the stored UTC
    boundaries are converted back into that same zone — a naive
    "treat local midnight as UTC" implementation would shift this by a day
    for negative-UTC-offset zones."""
    la = ZoneInfo("America/Los_Angeles")
    request_instant = datetime(2026, 7, 4, 12, 0, tzinfo=la)

    start_utc, end_utc = compute_all_day_utc_bounds(
        request_instant, request_instant, "America/Los_Angeles"
    )

    assert start_utc.astimezone(la).date().isoformat() == "2026-07-04"
    assert end_utc.astimezone(la).date().isoformat() == "2026-07-05"


def test_all_day_multi_day_range_spans_exact_number_of_days() -> None:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    end = datetime(2026, 8, 3, tzinfo=UTC)
    start_utc, end_utc = compute_all_day_utc_bounds(start, end, "Europe/Istanbul")
    assert (end_utc - start_utc) == timedelta(days=3)


def test_all_day_bounds_are_consistent_across_two_different_timezones() -> None:
    """Requesting the *same* intended calendar day, framed via two different
    timezones' local midday, must each independently round-trip to their own
    correct local day when read back in their own zone."""
    tokyo = ZoneInfo("Asia/Tokyo")
    ny = ZoneInfo("America/New_York")

    tokyo_request = datetime(2026, 11, 20, 9, 0, tzinfo=tokyo)
    ny_request = datetime(2026, 11, 20, 9, 0, tzinfo=ny)

    tokyo_start, tokyo_end = compute_all_day_utc_bounds(tokyo_request, tokyo_request, "Asia/Tokyo")
    ny_start, ny_end = compute_all_day_utc_bounds(ny_request, ny_request, "America/New_York")

    assert tokyo_start.astimezone(tokyo).date().isoformat() == "2026-11-20"
    assert ny_start.astimezone(ny).date().isoformat() == "2026-11-20"
    # The two zones' UTC instants for "the same calendar day" are genuinely
    # different instants — proving the function is timezone-driven, not a
    # blind UTC passthrough.
    assert tokyo_start != ny_start


# ── Service-level (DB-backed) ────────────────────────────────────────────────


async def test_all_day_request_uses_the_users_work_schedule_timezone() -> None:
    agency_id, user_id = await _create_agency_with_user("TimeOffTZ")
    async with AsyncSessionLocal() as session:
        await WorkScheduleService(session).upsert(
            agency_id,
            WorkScheduleCreate(
                user_id=user_id,
                timezone="America/New_York",
                days=[
                    WorkScheduleDayCreate(
                        weekday=d, is_working_day=d < 5, capacity_minutes=480 if d < 5 else 0
                    )
                    for d in range(7)
                ],
            ),
        )

    request_day = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    async with AsyncSessionLocal() as session:
        entry, _ = await TimeOffService(session).request(
            agency_id,
            TimeOffCreate(
                user_id=user_id,
                start_at=request_day,
                end_at=request_day,
                all_day=True,
                type="vacation",
            ),
        )

    ny = ZoneInfo("America/New_York")
    assert entry.start_at.astimezone(ny).date().isoformat() == "2026-09-14"
    assert entry.end_at.astimezone(ny).date().isoformat() == "2026-09-15"


async def test_all_day_request_falls_back_to_default_timezone_without_schedule() -> None:
    agency_id, user_id = await _create_agency_with_user("TimeOffNoSchedule")
    request_day = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    async with AsyncSessionLocal() as session:
        entry, _ = await TimeOffService(session).request(
            agency_id,
            TimeOffCreate(user_id=user_id, start_at=request_day, end_at=request_day, all_day=True),
        )

    istanbul = ZoneInfo("Europe/Istanbul")
    assert entry.start_at.astimezone(istanbul).date().isoformat() == "2026-05-01"


async def test_request_approve_flow() -> None:
    agency_id, user_id = await _create_agency_with_user("TimeOffApprove")
    request_day = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        entry, _ = await TimeOffService(session).request(
            agency_id,
            TimeOffCreate(
                user_id=user_id, start_at=request_day, end_at=request_day, type="vacation"
            ),
        )
    assert entry.status == "requested"

    async with AsyncSessionLocal() as session:
        approved, _ = await TimeOffService(session).approve(
            agency_id, entry.id, approved_by_id=user_id
        )
    assert approved.status == "approved"
    assert approved.approved_by_id == user_id
    assert approved.approved_at is not None


async def test_approving_twice_raises_conflict() -> None:
    agency_id, user_id = await _create_agency_with_user("TimeOffDoubleApprove")
    request_day = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        svc = TimeOffService(session)
        entry, _ = await svc.request(
            agency_id,
            TimeOffCreate(user_id=user_id, start_at=request_day, end_at=request_day, type="sick"),
        )
        await svc.approve(agency_id, entry.id, approved_by_id=user_id)
        with pytest.raises(ConflictError):
            await svc.approve(agency_id, entry.id, approved_by_id=user_id)


async def test_reject_flow_persists_notes() -> None:
    agency_id, user_id = await _create_agency_with_user("TimeOffReject")
    request_day = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        svc = TimeOffService(session)
        entry, _ = await svc.request(
            agency_id,
            TimeOffCreate(user_id=user_id, start_at=request_day, end_at=request_day, type="unpaid"),
        )
        rejected = await svc.reject(
            agency_id,
            entry.id,
            approved_by_id=user_id,
            data=TimeOffReject(notes="Not enough coverage"),
        )

    assert rejected.status == "rejected"
    assert rejected.notes == "Not enough coverage"


async def test_time_off_is_tenant_isolated() -> None:
    agency_a, user_a = await _create_agency_with_user("TimeOffTenantA")
    agency_b, user_b = await _create_agency_with_user("TimeOffTenantB")
    request_day = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        entry, _ = await TimeOffService(session).request(
            agency_a,
            TimeOffCreate(
                user_id=user_a, start_at=request_day, end_at=request_day, type="vacation"
            ),
        )

    async with AsyncSessionLocal() as session:
        with pytest.raises(NotFoundError):
            await TimeOffService(session).approve(agency_b, entry.id, approved_by_id=user_b)

"""RetainerService tests (plan §3/§7/§13): timezone-safe period-boundary
correctness across multiple timezones, included/used/remaining/overage
minute math, rollover on/off, and no double-counting (nor dropping) of a
`TimeEntry` at a period boundary.

Documented deviation (checked before writing, per the task's explicit
fallback instruction): `CommercialTerms` (Phase 3) has no `retainer_period`
field, so period cadence is a fixed **monthly** cadence anchored to
`CommercialTerms.valid_from` — see the docstring in
`app/services/retainer_service.py` for the full rationale.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from app.core.exceptions import ValidationError
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.commercial_terms import CommercialTerms
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.repositories.agency_settings import AgencySettingsRepository
from app.services.agency_settings_service import AgencySettingsService
from app.services.retainer_service import RetainerService, compute_current_period

# ── Pure-function period-boundary tests (no DB) ─────────────────────────────


def test_compute_current_period_basic_mid_month() -> None:
    period = compute_current_period(date(2026, 1, 15), "Europe/Istanbul", as_of=date(2026, 1, 20))
    assert period.period_start == date(2026, 1, 15)
    assert period.period_end == date(2026, 2, 14)


def test_compute_current_period_handles_day_clamping_across_months() -> None:
    # Anchor on the 31st: February has no 31st, so that period's end clamps
    # to Feb 28 rather than crashing or silently wrapping into March.
    period = compute_current_period(date(2026, 1, 31), "Europe/Istanbul", as_of=date(2026, 2, 5))
    assert period.period_start == date(2026, 1, 31)
    assert period.period_end == date(2026, 2, 27)  # next period starts Feb 28


def test_compute_current_period_differs_by_timezone_for_same_anchor() -> None:
    """Two timezones with different UTC offsets must produce different UTC
    instants for the same local calendar boundary — the core timezone-safety
    property (mirrors `TimeOffService.compute_all_day_utc_bounds`)."""
    istanbul = compute_current_period(date(2026, 3, 1), "Europe/Istanbul", as_of=date(2026, 3, 10))
    los_angeles = compute_current_period(
        date(2026, 3, 1), "America/Los_Angeles", as_of=date(2026, 3, 10)
    )
    assert istanbul.period_start == los_angeles.period_start == date(2026, 3, 1)
    assert istanbul.period_start_utc != los_angeles.period_start_utc
    # Istanbul (UTC+3) local midnight arrives earlier in absolute time than
    # Los Angeles (UTC-7/-8) local midnight for the same calendar date.
    assert istanbul.period_start_utc < los_angeles.period_start_utc


def test_compute_current_period_no_gap_or_overlap_between_consecutive_periods() -> None:
    period_a = compute_current_period(date(2026, 1, 15), "UTC", as_of=date(2026, 1, 20))
    period_b = compute_current_period(date(2026, 1, 15), "UTC", as_of=date(2026, 2, 20))
    assert period_a.period_end_utc == period_b.period_start_utc


# ── DB-integration fixtures ─────────────────────────────────────────────────


async def _make_user(session, label: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{label.lower()}-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="not-a-real-hash-test-fixture-only",
        full_name=f"Test {label}",
        user_type=UserType.AGENCY_USER.value,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    return user


async def _seed_retainer(
    label: str,
    *,
    anchor: date,
    included_minutes: int = 600,
    overage_rate_cents: int | None = 10_000,
    timezone: str = "Europe/Istanbul",
) -> dict:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        agency = Agency(id=uuid.uuid4(), name=f"{label} Agency", slug=f"{label.lower()}-{suffix}")
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name=f"{label} Brand",
            slug=f"{label.lower()}-brand-{suffix}",
            timezone=timezone,
        )
        session.add_all([agency, brand])
        await session.flush()

        user = await _make_user(session, f"{label}User")
        await session.flush()
        session.add(
            AgencyMember(
                id=uuid.uuid4(),
                agency_id=agency.id,
                user_id=user.id,
                role=AgencyMemberRole.OWNER.value,
                status=AgencyMemberStatus.ACTIVE.value,
            )
        )
        session.add(
            CommercialTerms(
                id=uuid.uuid4(),
                agency_id=agency.id,
                brand_id=brand.id,
                billing_model="retainer",
                currency="TRY",
                retainer_amount_cents=500_000,
                retainer_included_minutes=included_minutes,
                overage_rate_cents=overage_rate_cents,
                payment_terms_days=30,
                tax_rate_bps=0,
                valid_from=anchor,
                active=True,
            )
        )
        await session.commit()
        return {"agency_id": agency.id, "brand_id": brand.id, "user_id": user.id}


async def _add_time_entry(agency_id, brand_id, user_id, started_at, duration_minutes: int) -> None:
    async with AsyncSessionLocal() as session:
        entry = TimeEntry(
            id=uuid.uuid4(),
            agency_id=agency_id,
            brand_id=brand_id,
            user_id=user_id,
            category="design",
            started_at=started_at,
            ended_at=started_at + timedelta(minutes=duration_minutes),
            duration_seconds=duration_minutes * 60,
            billable=True,
            source="manual",
            locked=True,
        )
        session.add(entry)
        await session.commit()


# ── Included / used / remaining / overage math ──────────────────────────────


async def test_summary_computes_used_remaining_and_overage() -> None:
    anchor = date(2026, 1, 15)
    ctx = await _seed_retainer(
        "Math1", anchor=anchor, included_minutes=120, overage_rate_cents=10_000
    )
    period = compute_current_period(anchor, "Europe/Istanbul", as_of=date(2026, 1, 20))
    await _add_time_entry(
        ctx["agency_id"],
        ctx["brand_id"],
        ctx["user_id"],
        period.period_start_utc + timedelta(hours=2),
        duration_minutes=180,  # 3h logged, 2h included -> 1h overage
    )

    async with AsyncSessionLocal() as session:
        summary = await RetainerService(session).get_current_period_summary(
            ctx["agency_id"], ctx["brand_id"], as_of=date(2026, 1, 20)
        )

    assert summary.included_minutes == 120
    assert summary.used_minutes == 180
    assert summary.remaining_minutes == 0
    assert summary.overage_minutes == 60
    assert summary.overage_cost_cents == 10_000  # 1h * 10000 cents/hour


async def test_summary_reports_remaining_minutes_when_under_included() -> None:
    anchor = date(2026, 1, 15)
    ctx = await _seed_retainer("Math2", anchor=anchor, included_minutes=600)
    period = compute_current_period(anchor, "Europe/Istanbul", as_of=date(2026, 1, 20))
    await _add_time_entry(
        ctx["agency_id"], ctx["brand_id"], ctx["user_id"], period.period_start_utc, 120
    )

    async with AsyncSessionLocal() as session:
        summary = await RetainerService(session).get_current_period_summary(
            ctx["agency_id"], ctx["brand_id"], as_of=date(2026, 1, 20)
        )
    assert summary.used_minutes == 120
    assert summary.remaining_minutes == 480
    assert summary.overage_minutes == 0
    assert summary.overage_cost_cents == 0


# ── No double-counting / no dropped entries at a period boundary ───────────


async def test_entry_at_exact_boundary_counts_only_in_next_period() -> None:
    anchor = date(2026, 1, 15)
    ctx = await _seed_retainer("Boundary1", anchor=anchor, included_minutes=600)
    period = compute_current_period(anchor, "Europe/Istanbul", as_of=date(2026, 1, 20))

    # Exactly AT the boundary -> belongs to the NEXT period.
    await _add_time_entry(
        ctx["agency_id"], ctx["brand_id"], ctx["user_id"], period.period_end_utc, 30
    )
    # One second BEFORE the boundary -> belongs to THIS period.
    await _add_time_entry(
        ctx["agency_id"],
        ctx["brand_id"],
        ctx["user_id"],
        period.period_end_utc - timedelta(seconds=1),
        30,
    )

    async with AsyncSessionLocal() as session:
        current_summary = await RetainerService(session).get_current_period_summary(
            ctx["agency_id"], ctx["brand_id"], as_of=date(2026, 1, 20)
        )
    assert current_summary.used_minutes == 30  # only the pre-boundary entry

    next_as_of = period.period_end + timedelta(days=1)
    async with AsyncSessionLocal() as session:
        next_summary = await RetainerService(session).get_current_period_summary(
            ctx["agency_id"], ctx["brand_id"], as_of=next_as_of
        )
    assert next_summary.used_minutes == 30  # only the at-boundary entry

    # Total logged (60 min) is fully accounted for exactly once across the
    # two adjacent periods — neither double-counted nor dropped.
    assert current_summary.used_minutes + next_summary.used_minutes == 60


# ── Rollover on/off ──────────────────────────────────────────────────────────


async def test_rollover_disabled_by_default_no_extra_minutes() -> None:
    anchor = date(2026, 1, 15)
    ctx = await _seed_retainer("NoRollover1", anchor=anchor, included_minutes=120)
    period1 = compute_current_period(anchor, "Europe/Istanbul", as_of=date(2026, 1, 20))
    await _add_time_entry(
        ctx["agency_id"], ctx["brand_id"], ctx["user_id"], period1.period_start_utc, 30
    )  # 90 unused minutes in period 1

    next_as_of = period1.period_end + timedelta(days=1)
    async with AsyncSessionLocal() as session:
        summary = await RetainerService(session).get_current_period_summary(
            ctx["agency_id"], ctx["brand_id"], as_of=next_as_of
        )
    assert summary.rolled_over_minutes == 0
    assert summary.included_minutes == 120


async def test_rollover_enabled_carries_unused_minutes_forward_once() -> None:
    anchor = date(2026, 1, 15)
    ctx = await _seed_retainer("Rollover1", anchor=anchor, included_minutes=120)

    async with AsyncSessionLocal() as session:
        await AgencySettingsService(session).get_or_create(ctx["agency_id"])
    async with AsyncSessionLocal() as session:
        repo = AgencySettingsRepository(session)
        settings = await repo.get_by_agency(ctx["agency_id"])
        settings.retainer_default_rollover = True
        await session.commit()

    period1 = compute_current_period(anchor, "Europe/Istanbul", as_of=date(2026, 1, 20))
    await _add_time_entry(
        ctx["agency_id"], ctx["brand_id"], ctx["user_id"], period1.period_start_utc, 30
    )  # 90 unused minutes in period 1

    next_as_of = period1.period_end + timedelta(days=1)
    async with AsyncSessionLocal() as session:
        summary = await RetainerService(session).get_current_period_summary(
            ctx["agency_id"], ctx["brand_id"], as_of=next_as_of
        )
    assert summary.rolled_over_minutes == 90
    assert summary.included_minutes == 210  # 120 base + 90 rolled over


# ── Validation ───────────────────────────────────────────────────────────────


async def test_summary_rejects_brand_without_active_retainer_terms() -> None:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        agency = Agency(id=uuid.uuid4(), name="NoTerms Agency", slug=f"noterms-{suffix}")
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name="NoTerms Brand",
            slug=f"noterms-brand-{suffix}",
        )
        session.add_all([agency, brand])
        await session.commit()
        agency_id, brand_id = agency.id, brand.id

    async with AsyncSessionLocal() as session:
        with pytest.raises(ValidationError):
            await RetainerService(session).get_current_period_summary(agency_id, brand_id)

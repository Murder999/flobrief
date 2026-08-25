"""Time report tests: every aggregate (weekly/team/by-brand/by-brief/
missing/CSV export) is computed from real seeded TimeEntry rows — the
`tenants` fixture's one stopped, unlocked, billable "design" entry (1 hour,
today) on tenant_a.brief_id/brand_id — never fabricated numbers. Also
verifies TIME_ENTRY_VIEW_TEAM gates the team-scoped reports but not the
self-service weekly view."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from app.core.security import create_access_token
from app.core.time_utils import utc_today
from app.db.session import AsyncSessionLocal
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.tests.conftest import agency_headers

# The `tenants` fixture's TimeEntry is anchored to `datetime.now(UTC)` (see
# conftest.py), so "today" here must also be computed in UTC — not via the
# local-clock `date.today()` — otherwise this constant silently disagrees
# with the fixture data for ~3h/day on a non-UTC system clock (e.g.
# Europe/Istanbul, UTC+3, between 00:00-03:00 local time), which was the
# root cause of this test file's intermittent failures.
TODAY = utc_today()
YESTERDAY = TODAY - timedelta(days=1)


async def _add_agency_member(agency_id: uuid.UUID, role: str) -> tuple[uuid.UUID, str]:
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"{role}-{uuid.uuid4().hex[:8]}@test.local",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name=f"Test {role}",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        session.add(
            AgencyMember(
                id=uuid.uuid4(),
                agency_id=agency_id,
                user_id=user.id,
                role=role,
                status=AgencyMemberStatus.ACTIVE.value,
            )
        )
        await session.commit()
        return user.id, create_access_token(str(user.id))


async def test_weekly_timesheet_reflects_fixture_entry(client, tenants) -> None:
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/time-reports/weekly",
        params={"start_date": TODAY.isoformat(), "end_date": TODAY.isoformat()},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_hours"] == 1.0
    assert body["billable_hours"] == 1.0
    assert body["by_day"][TODAY.isoformat()] == 1.0
    assert len(body["entries"]) == 1


async def test_weekly_timesheet_for_peer_requires_view_team(client, tenants) -> None:
    tenant_a, _ = tenants
    designer_id, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    resp = await client.get(
        "/api/v1/time-reports/weekly",
        params={"user_id": str(tenant_a.agency_user_id)},
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


async def test_team_report_requires_view_team_permission(client, tenants) -> None:
    tenant_a, _ = tenants
    _, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    resp = await client.get(
        "/api/v1/time-reports/team",
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


async def test_team_report_includes_fixture_entry(client, tenants) -> None:
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/time-reports/team",
        params={"start_date": TODAY.isoformat(), "end_date": TODAY.isoformat()},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_hours"] == 1.0
    assert len(body["users"]) == 1
    assert body["users"][0]["user_id"] == str(tenant_a.agency_user_id)
    assert body["users"][0]["total_hours"] == 1.0


async def test_by_brand_report_includes_fixture_entry(client, tenants) -> None:
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/time-reports/by-brand",
        params={
            "brand_id": str(tenant_a.brand_id),
            "start_date": TODAY.isoformat(),
            "end_date": TODAY.isoformat(),
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_hours"] == 1.0
    assert body["billable_hours"] == 1.0
    assert body["brief_count"] == 1


async def test_by_brief_report_matches_brief_time_summary(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)

    report_resp = await client.get(
        "/api/v1/time-reports/by-brief",
        params={"brief_id": str(tenant_a.brief_id)},
        headers=headers,
    )
    summary_resp = await client.get(
        f"/api/v1/briefs/{tenant_a.brief_id}/time-summary", headers=headers
    )
    assert report_resp.status_code == 200
    assert summary_resp.status_code == 200
    assert report_resp.json()["actual_hours"] == summary_resp.json()["actual_hours"] == 1.0


async def test_non_manager_cannot_access_by_brief_report(client, tenants) -> None:
    tenant_a, _ = tenants
    _, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    resp = await client.get(
        "/api/v1/time-reports/by-brief",
        params={"brief_id": str(tenant_a.brief_id)},
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


async def test_missing_timesheet_flags_member_with_no_entries_yesterday(client, tenants) -> None:
    """The fixture entry is dated today, not yesterday, so tenant_a's ADMIN
    user must show up as missing for yesterday — a real, computed gap, not a
    hardcoded value."""
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/time-reports/missing",
        params={"start_date": YESTERDAY.isoformat(), "end_date": YESTERDAY.isoformat()},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    missing_user_ids = {m["user_id"] for m in body["missing"]}
    assert str(tenant_a.agency_user_id) in missing_user_ids


async def test_missing_timesheet_requires_view_team(client, tenants) -> None:
    tenant_a, _ = tenants
    _, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    resp = await client.get(
        "/api/v1/time-reports/missing",
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


async def test_export_csv_contains_fixture_entry_row(client, tenants) -> None:
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/time-reports/export.csv",
        params={"start_date": TODAY.isoformat(), "end_date": TODAY.isoformat()},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "postpiloter-time-entries-" in resp.headers["content-disposition"]
    text = resp.content.decode("utf-8-sig")
    lines = [ln for ln in text.strip().splitlines() if ln]
    assert lines[0].startswith("date,user,brief_id,brand_id,category")
    assert len(lines) == 2  # header + the one fixture entry
    assert "design" in lines[1]
    assert "Test Fixture User" in lines[1]
    assert "evet" in lines[1]  # billable=true -> "evet"


async def test_export_csv_requires_view_team(client, tenants) -> None:
    tenant_a, _ = tenants
    _, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    resp = await client.get(
        "/api/v1/time-reports/export.csv",
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


async def test_by_brand_report_zero_when_no_entries_in_range(client, tenants) -> None:
    """A date range that predates the fixture entry must show real zeros,
    never a fabricated non-zero total."""
    tenant_a, _ = tenants
    far_past = (datetime.now(UTC) - timedelta(days=365)).date()
    resp = await client.get(
        "/api/v1/time-reports/by-brand",
        params={
            "brand_id": str(tenant_a.brand_id),
            "start_date": far_past.isoformat(),
            "end_date": (far_past + timedelta(days=1)).isoformat(),
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_hours"] == 0.0
    assert body["entry_count"] == 0
    assert body["category_breakdown"] == []


def test_utc_today_ignores_local_clock_near_midnight_boundary(monkeypatch) -> None:
    """Regression test for the root cause of this file's intermittent
    failures: date-boundary helpers must derive "today" from
    `datetime.now(UTC)`, never from the local system clock (`date.today()`).
    We simulate an instant just before UTC midnight — the exact window
    where a server whose OS timezone is e.g. Europe/Istanbul (UTC+3) would
    have `date.today()` already reporting "tomorrow" while the UTC day
    (and every UTC-anchored `TimeEntry.started_at`) is still "today"."""
    from app.core import time_utils

    fixed_instant = datetime(2024, 3, 10, 23, 45, tzinfo=UTC)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_instant if tz is not None else fixed_instant.replace(tzinfo=None)

    monkeypatch.setattr(time_utils, "datetime", _FixedDatetime)

    assert time_utils.utc_today() == date(2024, 3, 10)
    assert time_utils.utc_now() == fixed_instant


def test_default_week_boundary_derives_from_utc_today(monkeypatch) -> None:
    """`_default_week()` (used by /weekly, /team, /missing, /export.csv
    when no explicit range is given) must compute its Monday-Sunday window
    from `utc_today()`, not the local-clock `date.today()` — otherwise a
    request made near local midnight on a non-UTC server would silently
    default to the wrong week relative to UTC-anchored TimeEntry rows."""
    from app.api.v1 import time_reports as time_reports_module

    fixed_today = date(2024, 3, 10)
    monkeypatch.setattr(time_reports_module, "utc_today", lambda: fixed_today)

    start, end = time_reports_module._default_week()
    expected_start = fixed_today - timedelta(days=fixed_today.weekday())
    assert start == expected_start
    assert end == expected_start + timedelta(days=6)

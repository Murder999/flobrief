"""Brief time-estimate tests: estimate/actual/remaining/variance are always
computed live from real seeded TimeEntry rows (never stored), and
BRIEF_ESTIMATE_OVERRUN fires exactly once, only on the not-over -> over
transition."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.notification import NotificationEvent
from app.services.notification_routes import build_notification_action_url
from app.tests.conftest import agency_headers

SUMMARY_URL = "/api/v1/briefs/{brief_id}/time-summary"
MANUAL_URL = "/api/v1/time-entries"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _set_estimate(client, tenant, hours: float) -> None:
    resp = await client.patch(
        f"/api/v1/briefs/{tenant.brief_id}",
        json={"estimated_hours": hours},
        headers=agency_headers(tenant.agency_token, tenant.agency_id),
    )
    assert resp.status_code == 200
    assert resp.json()["estimated_hours"] == hours


async def test_summary_reflects_fixture_entry_only(client, tenants) -> None:
    """The `tenants` fixture seeds exactly one 1-hour design entry on
    tenant_a.brief_id and no estimate — actual_hours must equal that real
    row's duration, and remaining/variance must be null with no estimate."""
    tenant_a, _ = tenants
    resp = await client.get(
        SUMMARY_URL.format(brief_id=tenant_a.brief_id),
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["actual_hours"] == 1.0
    assert body["estimated_hours"] is None
    assert body["remaining_hours"] is None
    assert body["variance_hours"] is None
    assert body["is_over_estimate"] is False
    assert body["entry_count"] == 1
    assert body["category_breakdown"] == [{"category": "design", "hours": 1.0, "entry_count": 1}]


async def test_summary_computes_remaining_and_variance_under_estimate(client, tenants) -> None:
    tenant_a, _ = tenants
    await _set_estimate(client, tenant_a, 5.0)

    resp = await client.get(
        SUMMARY_URL.format(brief_id=tenant_a.brief_id),
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    body = resp.json()
    assert body["estimated_hours"] == 5.0
    assert body["actual_hours"] == 1.0
    assert body["remaining_hours"] == 4.0
    assert body["variance_hours"] == -4.0
    assert body["is_over_estimate"] is False


async def test_estimate_overrun_fires_once_on_transition(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)

    # 1h already logged by the fixture; set a 2h estimate (not yet over).
    await _set_estimate(client, tenant_a, 2.0)

    # Push actual to 1h + 1.5h = 2.5h -> crosses the 2h estimate: transition #1.
    start = datetime.now(UTC) - timedelta(days=3)
    resp1 = await client.post(
        MANUAL_URL,
        json={
            "brief_id": str(tenant_a.brief_id),
            "category": "design",
            "started_at": _iso(start),
            "ended_at": _iso(start + timedelta(hours=1, minutes=30)),
        },
        headers=headers,
    )
    assert resp1.status_code == 201

    # Log more time while already over -> must NOT fire again.
    start2 = datetime.now(UTC) - timedelta(days=2)
    resp2 = await client.post(
        MANUAL_URL,
        json={
            "brief_id": str(tenant_a.brief_id),
            "category": "revision",
            "started_at": _iso(start2),
            "ended_at": _iso(start2 + timedelta(hours=1)),
        },
        headers=headers,
    )
    assert resp2.status_code == 201

    summary_resp = await client.get(SUMMARY_URL.format(brief_id=tenant_a.brief_id), headers=headers)
    summary = summary_resp.json()
    assert summary["actual_hours"] == 3.5
    assert summary["is_over_estimate"] is True

    async with AsyncSessionLocal() as session:
        events = (
            (
                await session.execute(
                    select(NotificationEvent).where(
                        NotificationEvent.event_type == "brief.estimate_overrun",
                        NotificationEvent.payload["brief_id"].astext == str(tenant_a.brief_id),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1, (
            "BRIEF_ESTIMATE_OVERRUN must fire exactly once, only on the "
            "not-over -> over transition"
        )
        action_url = build_notification_action_url(
            events[0].event_type, events[0].payload, "agency"
        )
        assert action_url == f"/dashboard/briefs/{tenant_a.brief_id}", (
            "BRIEF_ESTIMATE_OVERRUN must deep-link to its brief, not fall "
            "through to the notifications-list fallback"
        )


async def test_category_breakdown_groups_by_category(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    start = datetime.now(UTC) - timedelta(days=5)

    resp = await client.post(
        MANUAL_URL,
        json={
            "brief_id": str(tenant_a.brief_id),
            "category": "copywriting",
            "started_at": _iso(start),
            "ended_at": _iso(start + timedelta(minutes=30)),
        },
        headers=headers,
    )
    assert resp.status_code == 201

    summary_resp = await client.get(SUMMARY_URL.format(brief_id=tenant_a.brief_id), headers=headers)
    breakdown = {c["category"]: c for c in summary_resp.json()["category_breakdown"]}
    assert "design" in breakdown
    assert "copywriting" in breakdown
    assert breakdown["copywriting"]["hours"] == 0.5
    assert breakdown["copywriting"]["entry_count"] == 1


async def test_running_timer_excluded_from_actual_hours(client, tenants) -> None:
    """A running (unstopped) timer has no duration_seconds yet, so it must
    not be counted as actual time — only finalized entries are real hours."""
    _, tenant_b = tenants
    headers = agency_headers(tenant_b.agency_token, tenant_b.agency_id)

    resp = await client.get(SUMMARY_URL.format(brief_id=tenant_b.brief_id), headers=headers)
    before = resp.json()["actual_hours"]

    start_resp = await client.post(
        "/api/v1/time-entries/start",
        json={"brief_id": str(tenant_b.brief_id), "category": "design"},
        headers=headers,
    )
    assert start_resp.status_code == 201

    resp2 = await client.get(SUMMARY_URL.format(brief_id=tenant_b.brief_id), headers=headers)
    assert resp2.json()["actual_hours"] == before

    # Cleanup
    await client.post(
        f"/api/v1/time-entries/{start_resp.json()['id']}/stop", json={}, headers=headers
    )

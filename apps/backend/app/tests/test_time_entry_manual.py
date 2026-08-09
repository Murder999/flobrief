"""Manual time entry tests: end-before-start rejection, non-blocking overlap
warnings, the future-date block + confirm_future override, and cross-tenant
IDOR protection — all against real seeded rows, never fabricated numbers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.tests.conftest import agency_headers

MANUAL_URL = "/api/v1/time-entries"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@pytest.mark.asyncio
async def test_manual_entry_end_before_start_rejected(client, tenants) -> None:
    tenant_a, _ = tenants
    now = datetime.now(UTC)
    resp = await client.post(
        MANUAL_URL,
        json={
            "category": "design",
            "started_at": _iso(now),
            "ended_at": _iso(now - timedelta(hours=1)),
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_manual_entry_zero_duration_rejected(client, tenants) -> None:
    tenant_a, _ = tenants
    now = datetime.now(UTC) - timedelta(hours=3)
    resp = await client.post(
        MANUAL_URL,
        json={"category": "design", "started_at": _iso(now), "ended_at": _iso(now)},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_manual_entry_valid_creates_entry(client, tenants) -> None:
    tenant_a, _ = tenants
    start = datetime.now(UTC) - timedelta(days=1, hours=3)
    end = start + timedelta(hours=2)
    resp = await client.post(
        MANUAL_URL,
        json={
            "brief_id": str(tenant_a.brief_id),
            "category": "copywriting",
            "description": "Metin taslağı",
            "started_at": _iso(start),
            "ended_at": _iso(end),
            "billable": True,
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    body = resp.json()
    entry = body["entry"]
    assert entry["source"] == "manual"
    assert entry["duration_seconds"] == 7200
    assert entry["category"] == "copywriting"
    assert body["overlap_warning"] is False


@pytest.mark.asyncio
async def test_manual_entry_overlap_produces_warning_not_block(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    base = datetime.now(UTC) - timedelta(days=2)

    first = await client.post(
        MANUAL_URL,
        json={
            "category": "design",
            "started_at": _iso(base),
            "ended_at": _iso(base + timedelta(hours=2)),
        },
        headers=headers,
    )
    assert first.status_code == 201

    # Overlaps the first entry's [base, base+2h) window by one hour.
    second = await client.post(
        MANUAL_URL,
        json={
            "category": "revision",
            "started_at": _iso(base + timedelta(hours=1)),
            "ended_at": _iso(base + timedelta(hours=3)),
        },
        headers=headers,
    )
    assert second.status_code == 201
    body = second.json()
    assert body["overlap_warning"] is True
    # Non-blocking: the entry itself is still created.
    assert body["entry"]["duration_seconds"] == 7200


@pytest.mark.asyncio
async def test_manual_entry_future_dated_blocked_by_default(client, tenants) -> None:
    tenant_a, _ = tenants
    start = datetime.now(UTC) + timedelta(days=1)
    end = start + timedelta(hours=1)
    resp = await client.post(
        MANUAL_URL,
        json={"category": "design", "started_at": _iso(start), "ended_at": _iso(end)},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_manual_entry_future_dated_allowed_with_confirm(client, tenants) -> None:
    tenant_a, _ = tenants
    start = datetime.now(UTC) + timedelta(days=1)
    end = start + timedelta(hours=1)
    resp = await client.post(
        MANUAL_URL,
        json={
            "category": "design",
            "started_at": _iso(start),
            "ended_at": _iso(end),
            "confirm_future": True,
        },
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    assert resp.json()["entry"]["duration_seconds"] == 3600


@pytest.mark.asyncio
async def test_cross_tenant_get_returns_404(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    resp = await client.get(
        f"/api/v1/time-entries/{tenant_b.time_entry_id}",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_update_returns_404(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    resp = await client.patch(
        f"/api/v1/time-entries/{tenant_b.time_entry_id}",
        json={"description": "hacked"},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_delete_returns_404(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    resp = await client.delete(
        f"/api/v1/time-entries/{tenant_b.time_entry_id}",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 404

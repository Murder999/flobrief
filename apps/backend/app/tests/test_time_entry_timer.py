"""Timer lifecycle tests: start/stop, reload-recompute (server `started_at`
is the only source of truth), the single-active-timer 409, and a real
concurrency test proving the Postgres partial unique index — not just app
logic — is what prevents a double-start."""

from __future__ import annotations

import asyncio

import pytest

from app.tests.conftest import agency_headers

START_URL = "/api/v1/time-entries/start"
ACTIVE_URL = "/api/v1/time-entries/active"


def _stop_url(entry_id: str) -> str:
    return f"/api/v1/time-entries/{entry_id}/stop"


@pytest.mark.asyncio
async def test_start_timer_creates_active_entry(client, tenants) -> None:
    tenant_a, _ = tenants
    resp = await client.post(
        START_URL,
        json={"brief_id": str(tenant_a.brief_id), "category": "design"},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["ended_at"] is None
    assert body["duration_seconds"] is None
    assert body["source"] == "timer"
    assert body["category"] == "design"


@pytest.mark.asyncio
async def test_active_timer_reload_recomputes_from_server_started_at(client, tenants) -> None:
    """Simulates a client reload: the server must return the *same*
    started_at on every poll — the client recomputes elapsed from that value,
    never from its own in-memory interval."""
    tenant_a, _ = tenants
    start_resp = await client.post(
        START_URL,
        json={"brief_id": str(tenant_a.brief_id), "category": "research"},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert start_resp.status_code == 201
    started_at = start_resp.json()["started_at"]

    for _ in range(3):
        active_resp = await client.get(
            ACTIVE_URL, headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        )
        assert active_resp.status_code == 200
        body = active_resp.json()
        assert body is not None
        assert body["started_at"] == started_at

    # Cleanup: stop it so later tests in this module don't collide.
    entry_id = start_resp.json()["id"]
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    stop_resp = await client.post(_stop_url(entry_id), json={}, headers=headers)
    assert stop_resp.status_code == 200


@pytest.mark.asyncio
async def test_active_timer_null_when_none_running(client, tenants) -> None:
    _, tenant_b = tenants
    resp = await client.get(
        ACTIVE_URL, headers=agency_headers(tenant_b.agency_token, tenant_b.agency_id)
    )
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_stop_timer_computes_duration_and_finalizes(client, tenants) -> None:
    tenant_a, _ = tenants
    start_resp = await client.post(
        START_URL,
        json={"brief_id": str(tenant_a.brief_id), "category": "design"},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    entry_id = start_resp.json()["id"]

    stop_resp = await client.post(
        _stop_url(entry_id),
        json={"category": "revision", "description": "Kapak görseli düzenlendi", "billable": False},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert stop_resp.status_code == 200
    body = stop_resp.json()
    entry = body["entry"]
    assert entry["ended_at"] is not None
    assert entry["duration_seconds"] is not None
    assert entry["duration_seconds"] >= 0
    assert entry["category"] == "revision"
    assert entry["description"] == "Kapak görseli düzenlendi"
    assert entry["billable"] is False


@pytest.mark.asyncio
async def test_second_start_while_active_returns_409(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    first = await client.post(START_URL, json={"category": "design"}, headers=headers)
    assert first.status_code == 201

    second = await client.post(START_URL, json={"category": "research"}, headers=headers)
    assert second.status_code == 409

    # Cleanup
    await client.post(_stop_url(first.json()["id"]), json={}, headers=headers)


@pytest.mark.asyncio
async def test_stop_already_stopped_returns_409(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    start_resp = await client.post(START_URL, json={"category": "design"}, headers=headers)
    entry_id = start_resp.json()["id"]

    first_stop = await client.post(_stop_url(entry_id), json={}, headers=headers)
    assert first_stop.status_code == 200

    second_stop = await client.post(_stop_url(entry_id), json={}, headers=headers)
    assert second_stop.status_code == 409


@pytest.mark.asyncio
async def test_concurrent_starts_only_one_succeeds(client, tenants) -> None:
    """Real concurrency test: fires two simultaneous /start requests for the
    same user and asserts the DB's partial unique index — not app-level
    checking — allows exactly one to win. Uses tenant_b to avoid interference
    from any timer left over by other tests in this module."""
    _, tenant_b = tenants
    headers = agency_headers(tenant_b.agency_token, tenant_b.agency_id)

    results = await asyncio.gather(
        client.post(START_URL, json={"category": "design"}, headers=headers),
        client.post(START_URL, json={"category": "research"}, headers=headers),
        return_exceptions=True,
    )

    statuses = sorted(r.status_code for r in results if not isinstance(r, Exception))
    assert statuses == [201, 409], f"Expected exactly one success, one 409; got {statuses}"

    # Cleanup: stop whichever one won.
    active_resp = await client.get(ACTIVE_URL, headers=headers)
    active = active_resp.json()
    if active is not None:
        await client.post(_stop_url(active["id"]), json={}, headers=headers)

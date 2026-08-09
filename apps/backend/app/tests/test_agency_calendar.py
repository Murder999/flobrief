"""Tests for the agency operations calendar aggregation (root-cause fix for
the "0 içerik" bug): merges real CalendarItem rows, Brief milestone dates,
and Deliverable lifecycle events into one agency-scoped agenda.

Pure logic tests (filter/sort) need no DB. The rest hit a real local
Postgres test DB through the HTTP layer, using the two-tenant `tenants`
fixture plus direct session writes for date fields the fixture leaves unset.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.session import AsyncSessionLocal
from app.models.brand import Brand
from app.models.brief import Brief
from app.models.calendar import CalendarItem
from app.services.agency_calendar_service import (
    AgencyCalendarEntry,
    filter_and_sort_agency_entries,
)
from app.tests.conftest import agency_headers

# ── Pure filter/sort tests (no DB) ────────────────────────────────────────────


def _entry(**overrides) -> AgencyCalendarEntry:
    defaults = dict(
        id=f"item:{uuid.uuid4()}",
        source_type="manual",
        agency_id=uuid.uuid4(),
        title="Test entry",
        item_type="post",
        status="planned",
        priority="normal",
    )
    defaults.update(overrides)
    return AgencyCalendarEntry(**defaults)


def test_filter_by_status() -> None:
    entries = [_entry(status="planned"), _entry(status="published")]
    result = filter_and_sort_agency_entries(entries, status="published")
    assert len(result) == 1
    assert result[0].status == "published"


def test_filter_by_event_type() -> None:
    entries = [_entry(source_type="manual"), _entry(source_type="brief_start")]
    result = filter_and_sort_agency_entries(entries, event_type="brief_start")
    assert len(result) == 1
    assert result[0].source_type == "brief_start"


def test_filter_by_priority() -> None:
    entries = [_entry(priority="urgent"), _entry(priority="normal")]
    result = filter_and_sort_agency_entries(entries, priority="urgent")
    assert len(result) == 1
    assert result[0].priority == "urgent"


def test_filter_by_assignee() -> None:
    uid = uuid.uuid4()
    entries = [
        _entry(assignee_ids=[uid]),
        _entry(assignee_ids=[uuid.uuid4()]),
    ]
    result = filter_and_sort_agency_entries(entries, assignee_id=uid)
    assert len(result) == 1
    assert uid in result[0].assignee_ids


def test_sort_orders_by_publish_at_ascending() -> None:
    now = datetime.now(UTC)
    later = _entry(publish_at=now + timedelta(days=5))
    earlier = _entry(publish_at=now)
    result = filter_and_sort_agency_entries([later, earlier])
    assert result[0] is earlier
    assert result[1] is later


def test_sort_falls_back_to_due_at_when_no_publish_at() -> None:
    now = datetime.now(UTC)
    entries = [_entry(due_at=now + timedelta(days=1)), _entry(due_at=now)]
    result = filter_and_sort_agency_entries(entries)
    assert result[0].due_at == now


def test_no_filters_returns_all_entries_sorted() -> None:
    entries = [_entry() for _ in range(3)]
    result = filter_and_sort_agency_entries(entries)
    assert len(result) == 3


# ── Integration tests (real DB, HTTP layer) ───────────────────────────────────


AGENDA_URL = "/api/v1/calendar/agenda"


@pytest.mark.asyncio
async def test_agenda_empty_when_no_dates_set(client, tenants) -> None:
    """The `tenants` fixture's brief/deliverable have no date fields set, so
    the agenda must legitimately be empty — not fabricated content."""
    tenant_a, _ = tenants
    resp = await client.get(
        AGENDA_URL, headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_agenda_shows_all_five_brief_milestones(client, tenants) -> None:
    tenant_a, _ = tenants
    async with AsyncSessionLocal() as session:
        brief = await session.get(Brief, tenant_a.brief_id)
        brief.start_date = "2026-08-01"
        brief.draft_date = "2026-08-05"
        brief.feedback_date = "2026-08-10"
        brief.deadline = "2026-08-15"
        brief.publish_date = "2026-08-20"
        await session.commit()

    resp = await client.get(
        AGENDA_URL, headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    )
    assert resp.status_code == 200
    entries = resp.json()
    source_types = {e["source_type"] for e in entries}
    assert source_types == {
        "brief_start",
        "first_draft",
        "brand_feedback",
        "approval_deadline",
        "publish_date",
    }
    assert all(e["brief_id"] == str(tenant_a.brief_id) for e in entries)
    assert all(e["editable"] is False for e in entries)
    assert all(e["action_url"] == f"/dashboard/briefs/{tenant_a.brief_id}" for e in entries)


@pytest.mark.asyncio
async def test_agenda_shows_deliverable_submitted_and_revision(client, tenants) -> None:
    tenant_a, _ = tenants
    async with AsyncSessionLocal() as session:
        from app.models.deliverable import Deliverable

        deliverable = await session.get(Deliverable, tenant_a.deliverable_id)
        deliverable.submitted_at = datetime.now(UTC)
        deliverable.status = "revision_requested"
        await session.commit()

    resp = await client.get(
        AGENDA_URL, headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    )
    assert resp.status_code == 200
    entries = resp.json()
    source_types = {e["source_type"] for e in entries}
    assert "deliverable_submitted" in source_types
    assert "revision_requested" in source_types
    for e in entries:
        assert e["deliverable_id"] == str(tenant_a.deliverable_id)
        assert e["editable"] is False


@pytest.mark.asyncio
async def test_agenda_dedup_real_calendar_item_vs_brief_deadline(client, tenants) -> None:
    """A brief deadline that already has a linked, real CalendarItem (the
    legacy BriefService sync path) must appear once, not twice."""
    tenant_a, _ = tenants
    deadline_dt = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    async with AsyncSessionLocal() as session:
        brief = await session.get(Brief, tenant_a.brief_id)
        brief.deadline = "2026-09-01"
        session.add(
            CalendarItem(
                id=uuid.uuid4(),
                agency_id=tenant_a.agency_id,
                brand_id=tenant_a.brand_id,
                brief_id=tenant_a.brief_id,
                title=brief.title,
                item_type="campaign",
                platform="other",
                status="planned",
                due_at=deadline_dt,
            )
        )
        await session.commit()

    resp = await client.get(
        AGENDA_URL, headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    )
    assert resp.status_code == 200
    entries = resp.json()
    deadline_entries = [e for e in entries if e["brief_id"] == str(tenant_a.brief_id)]
    assert len(deadline_entries) == 1
    assert deadline_entries[0]["source_type"] == "manual"
    assert deadline_entries[0]["editable"] is True


@pytest.mark.asyncio
async def test_agenda_tenant_isolation(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    async with AsyncSessionLocal() as session:
        brief_a = await session.get(Brief, tenant_a.brief_id)
        brief_a.deadline = "2026-08-15"
        brief_b = await session.get(Brief, tenant_b.brief_id)
        brief_b.deadline = "2026-08-15"
        await session.commit()

    resp_a = await client.get(
        AGENDA_URL, headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    )
    resp_b = await client.get(
        AGENDA_URL, headers=agency_headers(tenant_b.agency_token, tenant_b.agency_id)
    )
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    ids_a = {e["brief_id"] for e in resp_a.json()}
    ids_b = {e["brief_id"] for e in resp_b.json()}
    assert str(tenant_a.brief_id) in ids_a
    assert str(tenant_a.brief_id) not in ids_b
    assert str(tenant_b.brief_id) in ids_b
    assert str(tenant_b.brief_id) not in ids_a


@pytest.mark.asyncio
async def test_agenda_brand_id_idor_returns_404(client, tenants) -> None:
    """Tenant A must not be able to filter the agenda by Tenant B's brand_id."""
    tenant_a, tenant_b = tenants
    resp = await client.get(
        AGENDA_URL,
        params={"brand_id": str(tenant_b.brand_id)},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agenda_brand_filter_narrows_to_one_brand(client, tenants) -> None:
    tenant_a, _ = tenants
    async with AsyncSessionLocal() as session:
        second_brand = Brand(
            id=uuid.uuid4(),
            agency_id=tenant_a.agency_id,
            name="Second Brand",
            slug=f"second-brand-{uuid.uuid4().hex[:8]}",
        )
        session.add(second_brand)
        await session.flush()
        second_brief = Brief(
            id=uuid.uuid4(),
            agency_id=tenant_a.agency_id,
            brand_id=second_brand.id,
            title="Second Brand Brief",
            status="draft",
            created_by_id=tenant_a.agency_user_id,
            deadline="2026-08-15",
        )
        session.add(second_brief)
        brief_a = await session.get(Brief, tenant_a.brief_id)
        brief_a.deadline = "2026-08-15"
        await session.commit()
        second_brand_id = second_brand.id

    resp = await client.get(
        AGENDA_URL,
        params={"brand_id": str(second_brand_id)},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) >= 1
    assert all(e["brand_id"] == str(second_brand_id) for e in entries)
    assert all(e["brief_id"] != str(tenant_a.brief_id) for e in entries)


@pytest.mark.asyncio
async def test_agenda_internal_only_filter_excludes_brand_entries(client, tenants) -> None:
    tenant_a, _ = tenants
    async with AsyncSessionLocal() as session:
        brief_a = await session.get(Brief, tenant_a.brief_id)
        brief_a.deadline = "2026-08-15"
        session.add(
            CalendarItem(
                id=uuid.uuid4(),
                agency_id=tenant_a.agency_id,
                brand_id=None,
                title="Ajans İçi Toplantı",
                item_type="meeting",
                platform="other",
                status="planned",
                publish_at=datetime(2026, 8, 12, 10, 0, tzinfo=UTC),
            )
        )
        await session.commit()

    resp_internal = await client.get(
        AGENDA_URL,
        params={"brand_id": "internal"},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    resp_all = await client.get(
        AGENDA_URL, headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    )
    assert resp_internal.status_code == 200
    internal_entries = resp_internal.json()
    assert len(internal_entries) == 1
    assert internal_entries[0]["brand_id"] is None
    assert internal_entries[0]["title"] == "Ajans İçi Toplantı"

    all_entries = resp_all.json()
    assert any(e["brand_id"] is None for e in all_entries)
    assert any(e["brief_id"] == str(tenant_a.brief_id) for e in all_entries)


@pytest.mark.asyncio
async def test_agenda_requires_auth(client) -> None:
    resp = await client.get(AGENDA_URL)
    assert resp.status_code in (401, 403)

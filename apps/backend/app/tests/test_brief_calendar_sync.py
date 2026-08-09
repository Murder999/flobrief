"""Brief–Calendar sync tests.

Covers:
- BriefCreate.add_to_calendar schema field (default True, explicit False)
- BriefDetail.linked_calendar_item_id field
- CalendarItemCreate with brief_id / due_at fields
- Calendar date-range OR logic: items appear when due_at OR publish_at is in range
- BriefService calendar sync condition logic
- HTTP auth layer on brief endpoints
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.schemas.brief import BriefCreate, BriefDetail
from app.schemas.calendar import CalendarItemCreate

# ── BriefCreate.add_to_calendar ───────────────────────────────────────────────


class TestBriefCreateAddToCalendar:
    def test_add_to_calendar_defaults_true(self) -> None:
        b = BriefCreate(title="Launch Campaign")
        assert b.add_to_calendar is True

    def test_add_to_calendar_explicit_false(self) -> None:
        b = BriefCreate(title="Launch Campaign", add_to_calendar=False)
        assert b.add_to_calendar is False

    def test_add_to_calendar_explicit_true(self) -> None:
        b = BriefCreate(title="Launch Campaign", add_to_calendar=True)
        assert b.add_to_calendar is True

    def test_add_to_calendar_with_deadline(self) -> None:
        b = BriefCreate(title="Campaign", deadline="2026-09-01", add_to_calendar=True)
        assert b.deadline == "2026-09-01"
        assert b.add_to_calendar is True

    def test_add_to_calendar_false_with_deadline_no_sync_intended(self) -> None:
        b = BriefCreate(title="Campaign", deadline="2026-09-01", add_to_calendar=False)
        assert b.deadline == "2026-09-01"
        assert b.add_to_calendar is False

    def test_add_to_calendar_no_deadline_does_not_matter(self) -> None:
        b = BriefCreate(title="Campaign", deadline=None, add_to_calendar=True)
        assert b.deadline is None
        assert b.add_to_calendar is True

    def test_sync_condition_requires_deadline(self) -> None:
        """Mirrors BriefService.create() guard: payload.deadline and payload.add_to_calendar"""
        b = BriefCreate(title="Campaign", deadline=None, add_to_calendar=True)
        should_sync = bool(b.deadline and b.add_to_calendar)
        assert should_sync is False

    def test_sync_condition_deadline_plus_add_to_calendar(self) -> None:
        b = BriefCreate(title="Campaign", deadline="2026-09-01", add_to_calendar=True)
        should_sync = bool(b.deadline and b.add_to_calendar)
        assert should_sync is True

    def test_sync_condition_deadline_but_disabled(self) -> None:
        b = BriefCreate(title="Campaign", deadline="2026-09-01", add_to_calendar=False)
        should_sync = bool(b.deadline and b.add_to_calendar)
        assert should_sync is False


# ── BriefDetail.linked_calendar_item_id ──────────────────────────────────────


class TestBriefDetailLinkedCalendarItem:
    def _make_brief_detail(self, linked_id: uuid.UUID | None) -> dict:
        return {
            "id": uuid.uuid4(),
            "agency_id": uuid.uuid4(),
            "brand_id": None,
            "template_id": None,
            "title": "Test Brief",
            "description": None,
            "status": "draft",
            "priority": "normal",
            "deadline": None,
            "created_by_id": uuid.uuid4(),
            "updated_by_id": None,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            "field_values": [],
            "assignees": [],
            "linked_calendar_item_id": linked_id,
        }

    def test_linked_calendar_item_id_none_when_no_calendar(self) -> None:
        d = BriefDetail.model_validate(self._make_brief_detail(None))
        assert d.linked_calendar_item_id is None

    def test_linked_calendar_item_id_set_when_linked(self) -> None:
        cal_id = uuid.uuid4()
        d = BriefDetail.model_validate(self._make_brief_detail(cal_id))
        assert d.linked_calendar_item_id == cal_id

    def test_linked_calendar_item_id_is_uuid(self) -> None:
        cal_id = uuid.uuid4()
        d = BriefDetail.model_validate(self._make_brief_detail(cal_id))
        assert isinstance(d.linked_calendar_item_id, uuid.UUID)


# ── CalendarItemCreate with brief_id / due_at ─────────────────────────────────


class TestCalendarItemCreateWithBrief:
    def test_create_calendar_item_with_brief_id(self) -> None:
        brief_id = uuid.uuid4()
        item = CalendarItemCreate(title="Campaign Deadline", brief_id=brief_id)
        assert item.brief_id == brief_id

    def test_create_calendar_item_with_due_at(self) -> None:
        due = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
        item = CalendarItemCreate(title="Campaign Deadline", due_at=due)
        assert item.due_at == due

    def test_brief_linked_item_has_no_publish_at(self) -> None:
        due = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
        item = CalendarItemCreate(title="Campaign", due_at=due)
        assert item.publish_at is None

    def test_auto_sync_item_type_campaign(self) -> None:
        item = CalendarItemCreate(title="Campaign", item_type="campaign")
        assert item.item_type == "campaign"

    def test_auto_sync_platform_other(self) -> None:
        item = CalendarItemCreate(title="Campaign", platform="other")
        assert item.platform == "other"

    def test_auto_sync_status_planned(self) -> None:
        item = CalendarItemCreate(title="Campaign", status="planned")
        assert item.status == "planned"

    def test_full_brief_linked_item(self) -> None:
        brief_id = uuid.uuid4()
        brand_id = uuid.uuid4()
        _ = uuid.uuid4()  # agency_id placeholder
        due = datetime(2026, 10, 15, 12, 0, 0, tzinfo=UTC)
        item = CalendarItemCreate(
            title="Q4 Brand Campaign",
            item_type="campaign",
            platform="other",
            status="planned",
            brief_id=brief_id,
            brand_id=brand_id,
            due_at=due,
        )
        assert item.brief_id == brief_id
        assert item.brand_id == brand_id
        assert item.due_at == due
        assert item.publish_at is None


# ── Calendar date-range OR logic ─────────────────────────────────────────────


class TestCalendarDateRangeOrLogic:
    """
    list_range() now uses:
        OR(
          (publish_at >= start AND publish_at <= end),
          (due_at >= start AND due_at <= end),
        )
    These tests verify the business rule without hitting the DB.
    """

    def _in_range(
        self,
        publish_at: datetime | None,
        due_at: datetime | None,
        start: datetime,
        end: datetime,
    ) -> bool:
        pub_match = publish_at is not None and start <= publish_at <= end
        due_match = due_at is not None and start <= due_at <= end
        return pub_match or due_match

    def test_publish_at_in_range_shows(self) -> None:
        start = datetime(2026, 9, 1, tzinfo=UTC)
        end = datetime(2026, 9, 30, tzinfo=UTC)
        assert self._in_range(datetime(2026, 9, 15, tzinfo=UTC), None, start, end)

    def test_due_at_in_range_shows(self) -> None:
        start = datetime(2026, 9, 1, tzinfo=UTC)
        end = datetime(2026, 9, 30, tzinfo=UTC)
        assert self._in_range(None, datetime(2026, 9, 20, tzinfo=UTC), start, end)

    def test_both_none_hidden(self) -> None:
        start = datetime(2026, 9, 1, tzinfo=UTC)
        end = datetime(2026, 9, 30, tzinfo=UTC)
        assert not self._in_range(None, None, start, end)

    def test_publish_at_out_due_at_in(self) -> None:
        start = datetime(2026, 9, 1, tzinfo=UTC)
        end = datetime(2026, 9, 30, tzinfo=UTC)
        # Brief-linked item: publish_at is None, due_at is in range
        assert self._in_range(
            None,
            datetime(2026, 9, 10, tzinfo=UTC),
            start,
            end,
        )

    def test_publish_at_in_due_at_out(self) -> None:
        start = datetime(2026, 9, 1, tzinfo=UTC)
        end = datetime(2026, 9, 30, tzinfo=UTC)
        assert self._in_range(
            datetime(2026, 9, 5, tzinfo=UTC),
            datetime(2026, 10, 5, tzinfo=UTC),
            start,
            end,
        )

    def test_both_out_of_range_hidden(self) -> None:
        start = datetime(2026, 9, 1, tzinfo=UTC)
        end = datetime(2026, 9, 30, tzinfo=UTC)
        assert not self._in_range(
            datetime(2026, 10, 5, tzinfo=UTC),
            datetime(2026, 10, 5, tzinfo=UTC),
            start,
            end,
        )

    def test_due_at_on_boundary_shows(self) -> None:
        start = datetime(2026, 9, 1, tzinfo=UTC)
        end = datetime(2026, 9, 30, tzinfo=UTC)
        assert self._in_range(None, datetime(2026, 9, 1, tzinfo=UTC), start, end)
        assert self._in_range(None, datetime(2026, 9, 30, tzinfo=UTC), start, end)

    def test_brief_item_auto_created_with_due_at_appears(self) -> None:
        """Simulates: brief with deadline=2026-09-01 → CalendarItem due_at at noon."""
        deadline_str = "2026-09-01"
        due_at = datetime.fromisoformat(f"{deadline_str}T12:00:00").replace(tzinfo=UTC)
        month_start = datetime(2026, 9, 1, 0, 0, 0, tzinfo=UTC)
        month_end = datetime(2026, 9, 30, 23, 59, 59, tzinfo=UTC)
        assert self._in_range(None, due_at, month_start, month_end)


# ── HTTP auth layer ───────────────────────────────────────────────────────────


class TestBriefCalendarHTTPAuth:
    @pytest.mark.asyncio
    async def test_brief_create_without_token_returns_401(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/briefs",
            json={"title": "Test", "add_to_calendar": True},
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_brief_get_without_token_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get(
            f"/api/v1/briefs/{uuid.uuid4()}",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_calendar_month_without_token_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/calendar/month?year=2026&month=9",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

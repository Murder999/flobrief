"""Brand-portal calendar agenda tests.

Covers:
- Brief-date -> milestone-type parsing and label mapping consistency
- BrandCalendarEntry schema construction and defaults
- CalendarItemCreate/Update schema validation for the new priority/milestone_type fields
- Pure filter/sort logic (status, event_type, priority, assignee) without a live DB
- HTTP: brand-portal calendar endpoint requires authentication
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.models.enums import CalendarMilestoneType
from app.schemas.calendar import CalendarItemCreate, CalendarItemUpdate
from app.services.brand_calendar_service import (
    _BRIEF_DATE_FIELD_TO_MILESTONE,
    MILESTONE_LABELS,
    BrandCalendarEntry,
    _parse_brief_date,
    filter_and_sort_entries,
)


class TestParseBriefDate:
    def test_parses_iso_date(self) -> None:
        assert _parse_brief_date("2026-09-01") == date(2026, 9, 1)

    def test_none_returns_none(self) -> None:
        assert _parse_brief_date(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_brief_date("") is None

    def test_malformed_string_returns_none(self) -> None:
        assert _parse_brief_date("not-a-date") is None


class TestMilestoneMappingConsistency:
    def test_every_mapped_milestone_has_a_label(self) -> None:
        for milestone_type in _BRIEF_DATE_FIELD_TO_MILESTONE.values():
            assert milestone_type in MILESTONE_LABELS

    def test_every_mapped_milestone_is_a_valid_enum_value(self) -> None:
        valid = {e.value for e in CalendarMilestoneType}
        for milestone_type in _BRIEF_DATE_FIELD_TO_MILESTONE.values():
            assert milestone_type in valid

    def test_five_brief_fields_are_mapped(self) -> None:
        assert set(_BRIEF_DATE_FIELD_TO_MILESTONE.keys()) == {
            "start_date",
            "draft_date",
            "feedback_date",
            "deadline",
            "publish_date",
        }

    def test_final_delivery_has_no_brief_field_mapping(self) -> None:
        # final_delivery is reserved for manually-created meeting/custom calendar
        # items (no dedicated Brief column backs it) — see plan design decision.
        assert "final_delivery" not in _BRIEF_DATE_FIELD_TO_MILESTONE.values()
        assert "final_delivery" in MILESTONE_LABELS


class TestBrandCalendarEntrySchema:
    def test_minimal_construction_defaults_empty_assignees(self) -> None:
        entry = BrandCalendarEntry(
            id="milestone:x:brief_start",
            kind="brief_milestone",
            event_type="brief_start",
            title="Launch — Brief Başlangıcı",
            entry_date=date(2026, 8, 1),
            priority="normal",
            status="draft",
        )
        assert entry.assignee_ids == []
        assert entry.assignee_names == []
        assert entry.entry_time is None
        assert entry.brief_id is None

    def test_calendar_item_entry_with_time_and_assignees(self) -> None:
        uid = uuid.uuid4()
        entry = BrandCalendarEntry(
            id="item:1",
            kind="calendar_item",
            event_type="post",
            title="Instagram Post",
            entry_date=date(2026, 8, 5),
            entry_time=datetime(2026, 8, 5, 14, 30),
            priority="high",
            status="scheduled",
            assignee_ids=[uid],
            assignee_names=["Ayşe Yılmaz"],
        )
        assert entry.assignee_ids == [uid]
        assert entry.entry_time.hour == 14


class TestCalendarItemCreateValidation:
    def test_default_priority_is_normal(self) -> None:
        item = CalendarItemCreate(title="Post")
        assert item.priority == "normal"
        assert item.milestone_type is None

    def test_meeting_type_accepted(self) -> None:
        item = CalendarItemCreate(title="Kickoff toplantısı", item_type="meeting")
        assert item.item_type == "meeting"

    def test_custom_type_accepted(self) -> None:
        item = CalendarItemCreate(title="Özel etkinlik", item_type="custom")
        assert item.item_type == "custom"

    def test_invalid_priority_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CalendarItemCreate(title="Post", priority="critical")

    def test_valid_milestone_type_accepted(self) -> None:
        item = CalendarItemCreate(
            title="Final teslim toplantısı",
            item_type="meeting",
            milestone_type="final_delivery",
        )
        assert item.milestone_type == "final_delivery"

    def test_invalid_milestone_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CalendarItemCreate(title="Post", milestone_type="not_a_real_milestone")


class TestCalendarItemUpdateValidation:
    def test_partial_update_priority_only(self) -> None:
        upd = CalendarItemUpdate(priority="urgent")
        assert upd.priority == "urgent"
        assert upd.title is None

    def test_invalid_priority_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CalendarItemUpdate(priority="whenever")


class TestFilterAndSortEntries:
    def _entry(self, **overrides) -> BrandCalendarEntry:
        base = dict(
            id=str(uuid.uuid4()),
            kind="calendar_item",
            event_type="post",
            title="Entry",
            entry_date=date(2026, 8, 1),
            priority="normal",
            status="planned",
        )
        base.update(overrides)
        return BrandCalendarEntry(**base)

    def test_sorts_by_date_then_time(self) -> None:
        e1 = self._entry(entry_date=date(2026, 8, 2))
        e2 = self._entry(entry_date=date(2026, 8, 1), entry_time=datetime(2026, 8, 1, 9))
        e3 = self._entry(entry_date=date(2026, 8, 1), entry_time=datetime(2026, 8, 1, 8))
        result = filter_and_sort_entries([e1, e2, e3])
        assert [e.id for e in result] == [e3.id, e2.id, e1.id]

    def test_filters_by_status(self) -> None:
        planned = self._entry(status="planned")
        approved = self._entry(status="approved")
        result = filter_and_sort_entries([planned, approved], status="approved")
        assert result == [approved]

    def test_filters_by_event_type(self) -> None:
        post = self._entry(event_type="post")
        meeting = self._entry(event_type="meeting")
        result = filter_and_sort_entries([post, meeting], event_type="meeting")
        assert result == [meeting]

    def test_filters_by_priority(self) -> None:
        low = self._entry(priority="low")
        urgent = self._entry(priority="urgent")
        result = filter_and_sort_entries([low, urgent], priority="urgent")
        assert result == [urgent]

    def test_filters_by_assignee(self) -> None:
        uid_a, uid_b = uuid.uuid4(), uuid.uuid4()
        entry_a = self._entry(assignee_ids=[uid_a])
        entry_b = self._entry(assignee_ids=[uid_b])
        result = filter_and_sort_entries([entry_a, entry_b], assignee_id=uid_a)
        assert result == [entry_a]

    def test_no_filters_returns_all_sorted(self) -> None:
        e1 = self._entry(entry_date=date(2026, 8, 3))
        e2 = self._entry(entry_date=date(2026, 8, 1))
        result = filter_and_sort_entries([e1, e2])
        assert len(result) == 2
        assert result[0].entry_date == date(2026, 8, 1)


class TestBrandCalendarHTTP:
    @pytest.mark.asyncio
    async def test_calendar_requires_authentication(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/brand-portal/calendar")
        assert resp.status_code in (401, 403)

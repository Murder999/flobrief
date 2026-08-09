"""Unit tests for calendar models, schemas, and business logic.

No DB required — pure Python logic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.enums import CalendarItemStatus, CalendarItemType, CalendarPlatform
from app.schemas.calendar import (
    CalendarItemCreate,
    CalendarItemUpdate,
    StatusChangeRequest,
)

# ── Enum value tests ──────────────────────────────────────────────────────────


def test_calendar_item_type_values() -> None:
    assert CalendarItemType.POST == "post"
    assert CalendarItemType.STORY == "story"
    assert CalendarItemType.REELS == "reels"
    assert CalendarItemType.VIDEO == "video"
    assert CalendarItemType.CAMPAIGN == "campaign"
    assert CalendarItemType.BLOG == "blog"
    assert CalendarItemType.EMAIL == "email"
    assert CalendarItemType.AD_CREATIVE == "ad_creative"


def test_calendar_platform_values() -> None:
    assert CalendarPlatform.INSTAGRAM == "instagram"
    assert CalendarPlatform.FACEBOOK == "facebook"
    assert CalendarPlatform.TIKTOK == "tiktok"
    assert CalendarPlatform.LINKEDIN == "linkedin"
    assert CalendarPlatform.X == "x"
    assert CalendarPlatform.YOUTUBE == "youtube"
    assert CalendarPlatform.WEBSITE == "website"
    assert CalendarPlatform.EMAIL == "email"
    assert CalendarPlatform.OTHER == "other"


def test_calendar_item_status_values() -> None:
    assert CalendarItemStatus.PLANNED == "planned"
    assert CalendarItemStatus.IN_DESIGN == "in_design"
    assert CalendarItemStatus.WAITING_APPROVAL == "waiting_approval"
    assert CalendarItemStatus.APPROVED == "approved"
    assert CalendarItemStatus.SCHEDULED == "scheduled"
    assert CalendarItemStatus.PUBLISHED == "published"
    assert CalendarItemStatus.CANCELLED == "cancelled"


# ── CalendarItemCreate validation ─────────────────────────────────────────────


def test_create_valid_minimal() -> None:
    item = CalendarItemCreate(title="Summer Campaign")
    assert item.title == "Summer Campaign"
    assert item.item_type == "post"
    assert item.platform == "other"
    assert item.status == "planned"
    assert item.brand_id is None
    assert item.brief_id is None


def test_create_empty_title_raises() -> None:
    with pytest.raises(ValidationError):
        CalendarItemCreate(title="   ")


def test_create_title_stripped() -> None:
    item = CalendarItemCreate(title="  My Post  ")
    assert item.title == "My Post"


def test_create_invalid_item_type_raises() -> None:
    with pytest.raises(ValidationError):
        CalendarItemCreate(title="Test", item_type="banner")


def test_create_invalid_platform_raises() -> None:
    with pytest.raises(ValidationError):
        CalendarItemCreate(title="Test", platform="snapchat")


def test_create_invalid_status_raises() -> None:
    with pytest.raises(ValidationError):
        CalendarItemCreate(title="Test", status="draft")


def test_create_all_valid_types() -> None:
    for t in CalendarItemType:
        item = CalendarItemCreate(title="X", item_type=t.value)
        assert item.item_type == t.value


def test_create_all_valid_platforms() -> None:
    for p in CalendarPlatform:
        item = CalendarItemCreate(title="X", platform=p.value)
        assert item.platform == p.value


def test_create_all_valid_statuses() -> None:
    for s in CalendarItemStatus:
        item = CalendarItemCreate(title="X", status=s.value)
        assert item.status == s.value


def test_create_with_publish_at() -> None:
    dt = datetime(2026, 8, 15, 10, 0, 0, tzinfo=UTC)
    item = CalendarItemCreate(title="Test", platform="instagram", publish_at=dt)
    assert item.publish_at == dt


def test_create_with_brand_and_brief() -> None:
    brand_id = uuid.uuid4()
    brief_id = uuid.uuid4()
    item = CalendarItemCreate(title="Test", brand_id=brand_id, brief_id=brief_id)
    assert item.brand_id == brand_id
    assert item.brief_id == brief_id


# ── CalendarItemUpdate validation ─────────────────────────────────────────────


def test_update_empty_payload_valid() -> None:
    update = CalendarItemUpdate()
    assert update.model_dump(exclude_unset=True) == {}


def test_update_title_only() -> None:
    update = CalendarItemUpdate(title="New Title")
    assert update.title == "New Title"


def test_update_empty_title_raises() -> None:
    with pytest.raises(ValidationError):
        CalendarItemUpdate(title="")


def test_update_invalid_type_raises() -> None:
    with pytest.raises(ValidationError):
        CalendarItemUpdate(item_type="unknown_type")


def test_update_invalid_platform_raises() -> None:
    with pytest.raises(ValidationError):
        CalendarItemUpdate(platform="twitter")  # "x" is correct


def test_update_valid_platform_x() -> None:
    update = CalendarItemUpdate(platform="x")
    assert update.platform == "x"


# ── StatusChangeRequest ───────────────────────────────────────────────────────


def test_status_change_valid() -> None:
    req = StatusChangeRequest(new_status="published")
    assert req.new_status == "published"


def test_status_change_invalid_raises() -> None:
    with pytest.raises(ValidationError):
        StatusChangeRequest(new_status="deleted")


def test_status_change_to_cancelled() -> None:
    req = StatusChangeRequest(new_status="cancelled")
    assert req.new_status == "cancelled"


# ── Business logic ────────────────────────────────────────────────────────────


def test_all_status_transitions_are_valid_enums() -> None:
    valid = {s.value for s in CalendarItemStatus}
    assert "planned" in valid
    assert "published" in valid
    assert "cancelled" in valid


def test_calendar_item_type_count() -> None:
    assert len(CalendarItemType) == 10


def test_calendar_platform_count() -> None:
    assert len(CalendarPlatform) == 9


def test_calendar_status_count() -> None:
    assert len(CalendarItemStatus) == 7

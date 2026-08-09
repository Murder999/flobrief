"""Unit tests for brief schemas, enums, and service logic."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.models.enums import BriefPriority, BriefStatus
from app.schemas.brief import BriefCreate, BriefUpdate

# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


def test_brief_status_values() -> None:
    assert BriefStatus.DRAFT == "draft"
    assert BriefStatus.IN_REVIEW == "in_review"
    assert BriefStatus.REVISION_REQUESTED == "revision_requested"
    assert BriefStatus.APPROVED == "approved"
    assert BriefStatus.ARCHIVED == "archived"


def test_brief_priority_values() -> None:
    assert BriefPriority.LOW == "low"
    assert BriefPriority.NORMAL == "normal"
    assert BriefPriority.HIGH == "high"
    assert BriefPriority.URGENT == "urgent"


# ---------------------------------------------------------------------------
# Schema: BriefCreate
# ---------------------------------------------------------------------------


def test_brief_create_minimal() -> None:
    b = BriefCreate(title="My brief")
    assert b.title == "My brief"
    assert b.priority == BriefPriority.NORMAL
    assert b.deadline is None
    assert b.template_id is None
    assert b.brand_id is None


def test_brief_create_strips_title_whitespace() -> None:
    b = BriefCreate(title="  Campaign  ")
    assert b.title == "Campaign"


def test_brief_create_empty_title_raises() -> None:
    with pytest.raises(ValidationError):
        BriefCreate(title="   ")


def test_brief_create_deadline_valid() -> None:
    b = BriefCreate(title="X", deadline="2026-08-15")
    assert b.deadline == "2026-08-15"


def test_brief_create_deadline_invalid_format_raises() -> None:
    with pytest.raises(ValidationError):
        BriefCreate(title="X", deadline="15/08/2026")


def test_brief_create_deadline_none_allowed() -> None:
    b = BriefCreate(title="X", deadline=None)
    assert b.deadline is None


def test_brief_create_multi_platform_and_content_type() -> None:
    b = BriefCreate(
        title="X",
        platforms=["instagram", "tiktok", "youtube"],
        content_types=["post", "reels", "story"],
    )
    assert b.platforms == ["instagram", "tiktok", "youtube"]
    assert b.content_types == ["post", "reels", "story"]


def test_brief_create_planning_dates_in_order_allowed() -> None:
    b = BriefCreate(
        title="X",
        start_date="2026-01-01",
        draft_date="2026-01-05",
        feedback_date="2026-01-10",
        deadline="2026-01-15",
        publish_date="2026-01-20",
    )
    assert b.deadline == "2026-01-15"


def test_brief_create_planning_dates_out_of_order_raises() -> None:
    with pytest.raises(ValidationError):
        BriefCreate(title="X", start_date="2026-01-15", draft_date="2026-01-01")


def test_brief_create_deadline_before_start_date_raises() -> None:
    with pytest.raises(ValidationError):
        BriefCreate(title="X", start_date="2026-02-01", deadline="2026-01-01")


def test_brief_create_publish_before_deadline_raises() -> None:
    with pytest.raises(ValidationError):
        BriefCreate(title="X", deadline="2026-02-01", publish_date="2026-01-01")


def test_brief_create_with_ids() -> None:
    tid = uuid.uuid4()
    bid = uuid.uuid4()
    b = BriefCreate(
        title="Campaign",
        template_id=tid,
        brand_id=bid,
        priority=BriefPriority.HIGH,
        deadline="2026-12-31",
    )
    assert b.template_id == tid
    assert b.brand_id == bid
    assert b.priority == BriefPriority.HIGH


# ---------------------------------------------------------------------------
# Schema: BriefUpdate
# ---------------------------------------------------------------------------


def test_brief_update_partial() -> None:
    u = BriefUpdate(title="New title")
    assert u.title == "New title"
    assert u.description is None
    assert u.priority is None


def test_brief_update_deadline_invalid_raises() -> None:
    with pytest.raises(ValidationError):
        BriefUpdate(deadline="2026.12.31")


def test_brief_update_empty_payload() -> None:
    u = BriefUpdate()
    dumped = u.model_dump(exclude_unset=True)
    assert dumped == {}


# ---------------------------------------------------------------------------
# Status transition logic
# ---------------------------------------------------------------------------


def test_status_transition_table() -> None:
    from app.services.brief_service import _STATUS_TRANSITIONS

    assert BriefStatus.IN_REVIEW in _STATUS_TRANSITIONS[BriefStatus.DRAFT]
    assert BriefStatus.ARCHIVED in _STATUS_TRANSITIONS[BriefStatus.DRAFT]
    assert BriefStatus.APPROVED in _STATUS_TRANSITIONS[BriefStatus.IN_REVIEW]
    assert _STATUS_TRANSITIONS[BriefStatus.ARCHIVED] == []

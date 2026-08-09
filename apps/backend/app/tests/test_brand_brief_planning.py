"""Tests for brand-portal brief planning fields: multi-select content types
with legacy singular fallback, planning-date ordering, and reject-reason
enforcement — added alongside the brand-portal Part 1 hardening pass."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.v1.brand_portal import BrandBriefCreate, BrandBriefUpdate, BrandRejectRequest


def test_brand_brief_create_multi_content_types() -> None:
    b = BrandBriefCreate(title="X", content_types=["post", "story", "reels"])
    assert b.content_types == ["post", "story", "reels"]


def test_brand_brief_create_legacy_singular_content_type_becomes_list() -> None:
    b = BrandBriefCreate(title="X", content_type="post")
    assert b.content_types == ["post"]


def test_brand_brief_create_content_types_takes_precedence_over_singular() -> None:
    b = BrandBriefCreate(title="X", content_type="post", content_types=["story"])
    assert b.content_types == ["story"]


def test_brand_brief_create_planning_dates_in_order_allowed() -> None:
    b = BrandBriefCreate(
        title="X",
        start_date="2026-01-01",
        draft_date="2026-01-05",
        feedback_date="2026-01-10",
        deadline="2026-01-15",
        publish_date="2026-01-20",
    )
    assert b.publish_date == "2026-01-20"


def test_brand_brief_create_planning_dates_out_of_order_raises() -> None:
    with pytest.raises(ValidationError):
        BrandBriefCreate(title="X", deadline="2026-01-20", publish_date="2026-01-01")


def test_brand_brief_update_legacy_singular_content_type_becomes_list() -> None:
    u = BrandBriefUpdate(content_type="banner")
    assert u.content_types == ["banner"]


def test_brand_brief_update_planning_dates_out_of_order_raises() -> None:
    with pytest.raises(ValidationError):
        BrandBriefUpdate(start_date="2026-02-01", draft_date="2026-01-01")


def test_brand_reject_request_requires_nonempty_reason() -> None:
    with pytest.raises(ValidationError):
        BrandRejectRequest(reason="   ")


def test_brand_reject_request_accepts_reason() -> None:
    r = BrandRejectRequest(reason="İçerik marka kimliğine uygun değil")
    assert r.reason == "İçerik marka kimliğine uygun değil"

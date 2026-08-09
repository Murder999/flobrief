"""Tests for brand portal brief request creation and management."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.v1.brand_portal import BrandBriefCreate, BrandBriefUpdate
from app.schemas.brief import BriefRead

# ---------------------------------------------------------------------------
# BrandBriefCreate schema validation
# ---------------------------------------------------------------------------


def test_brand_brief_create_minimal() -> None:
    b = BrandBriefCreate(title="Yaz Kampanyası")
    assert b.title == "Yaz Kampanyası"
    assert b.priority == "normal"
    assert b.platforms == []
    assert b.reference_links == []
    assert b.deadline is None


def test_brand_brief_create_strips_title() -> None:
    b = BrandBriefCreate(title="  Kampanya  ")
    assert b.title == "Kampanya"


def test_brand_brief_create_empty_title_raises() -> None:
    with pytest.raises(ValidationError):
        BrandBriefCreate(title="   ")


def test_brand_brief_create_valid_deadline() -> None:
    b = BrandBriefCreate(title="X", deadline="2026-09-01")
    assert b.deadline == "2026-09-01"


def test_brand_brief_create_invalid_deadline_raises() -> None:
    with pytest.raises(ValidationError):
        BrandBriefCreate(title="X", deadline="01/09/2026")


def test_brand_brief_create_valid_priority() -> None:
    for p in ("low", "normal", "high", "urgent"):
        b = BrandBriefCreate(title="X", priority=p)
        assert b.priority == p


def test_brand_brief_create_invalid_priority_raises() -> None:
    with pytest.raises(ValidationError):
        BrandBriefCreate(title="X", priority="critical")


def test_brand_brief_create_full() -> None:
    b = BrandBriefCreate(
        title="Instagram Kampanyası",
        description="Yaz koleksiyonu için içerik",
        campaign_goal="Marka bilinirliğini artırmak",
        target_audience="18-35 yaş kadın",
        platforms=["instagram", "tiktok"],
        content_type="reels",
        priority="high",
        deadline="2026-08-15",
        publish_date="2026-08-20",
        cta="Hemen incele",
        brand_tone="Samimi, eğlenceli",
        reference_links=["https://example.com/ref1"],
        additional_notes="Marka renklerine dikkat edilsin",
    )
    assert b.platforms == ["instagram", "tiktok"]
    assert b.priority == "high"
    assert b.publish_date == "2026-08-20"


# ---------------------------------------------------------------------------
# BrandBriefUpdate schema validation
# ---------------------------------------------------------------------------


def test_brand_brief_update_all_optional() -> None:
    u = BrandBriefUpdate()
    assert u.title is None
    assert u.priority is None
    assert u.platforms is None


def test_brand_brief_update_invalid_date_raises() -> None:
    with pytest.raises(ValidationError):
        BrandBriefUpdate(deadline="bad-date")


def test_brand_brief_update_valid_date() -> None:
    u = BrandBriefUpdate(deadline="2026-12-01")
    assert u.deadline == "2026-12-01"


# ---------------------------------------------------------------------------
# BriefRead schema includes source and meta
# ---------------------------------------------------------------------------


def test_brief_read_has_source_and_meta_fields() -> None:
    import uuid
    from datetime import datetime

    now = datetime.utcnow()
    uid = uuid.uuid4()
    b = BriefRead(
        id=uid,
        agency_id=uid,
        brand_id=None,
        template_id=None,
        title="Test Brief",
        description=None,
        status="draft",
        priority="normal",
        deadline=None,
        source="brand_portal",
        meta={"platforms": ["instagram"], "content_type": "post"},
        created_by_id=uid,
        updated_by_id=None,
        created_at=now,
        updated_at=now,
    )
    assert b.source == "brand_portal"
    assert b.meta is not None
    assert b.meta["platforms"] == ["instagram"]


def test_brief_read_source_defaults_none() -> None:
    import uuid
    from datetime import datetime

    now = datetime.utcnow()
    uid = uuid.uuid4()
    b = BriefRead(
        id=uid,
        agency_id=uid,
        brand_id=None,
        template_id=None,
        title="Test Brief",
        description=None,
        status="draft",
        priority="normal",
        deadline=None,
        created_by_id=uid,
        updated_by_id=None,
        created_at=now,
        updated_at=now,
    )
    assert b.source is None
    assert b.meta is None


def test_brief_read_falls_back_to_meta_for_legacy_platforms_and_content_types() -> None:
    """Old brief rows only ever wrote platforms/content_types into `meta` JSON —
    BriefRead must still surface them even though the typed columns are empty."""
    import uuid
    from datetime import datetime

    now = datetime.utcnow()
    uid = uuid.uuid4()
    b = BriefRead(
        id=uid,
        agency_id=uid,
        brand_id=None,
        template_id=None,
        title="Legacy Brief",
        description=None,
        status="draft",
        priority="normal",
        deadline=None,
        platforms=None,
        content_types=None,
        meta={"platforms": ["tiktok", "youtube"], "content_types": ["reels"]},
        created_by_id=uid,
        updated_by_id=None,
        created_at=now,
        updated_at=now,
    )
    assert b.platforms == ["tiktok", "youtube"]
    assert b.content_types == ["reels"]


def test_brief_read_prefers_typed_columns_over_meta() -> None:
    import uuid
    from datetime import datetime

    now = datetime.utcnow()
    uid = uuid.uuid4()
    b = BriefRead(
        id=uid,
        agency_id=uid,
        brand_id=None,
        template_id=None,
        title="New Brief",
        description=None,
        status="draft",
        priority="normal",
        deadline=None,
        platforms=["instagram"],
        content_types=["post"],
        meta={"platforms": ["tiktok"], "content_types": ["reels"]},
        created_by_id=uid,
        updated_by_id=None,
        created_at=now,
        updated_at=now,
    )
    assert b.platforms == ["instagram"]
    assert b.content_types == ["post"]


# ---------------------------------------------------------------------------
# Status flow: accepted separates agency acceptance from brand approval
# ---------------------------------------------------------------------------


def test_brief_status_enum_has_accepted() -> None:
    from app.models.enums import BriefStatus

    assert BriefStatus.ACCEPTED == "accepted"
    assert "accepted" in [s.value for s in BriefStatus]


def test_brief_status_enum_has_approved_separate_from_accepted() -> None:
    from app.models.enums import BriefStatus

    assert BriefStatus.ACCEPTED != BriefStatus.APPROVED
    assert BriefStatus.ACCEPTED.value == "accepted"
    assert BriefStatus.APPROVED.value == "approved"


def test_status_transition_in_review_to_accepted_allowed() -> None:
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.IN_REVIEW]
    assert BriefStatus.ACCEPTED in allowed


def test_status_transition_in_review_to_approved_allowed_for_agency_briefs() -> None:
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.IN_REVIEW]
    assert BriefStatus.APPROVED in allowed


def test_status_transition_accepted_to_in_production_allowed() -> None:
    """Agency moves an accepted brief to in_production (new workflow)."""
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.ACCEPTED]
    assert BriefStatus.IN_PRODUCTION in allowed


def test_status_transition_accepted_cannot_go_to_draft() -> None:
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.ACCEPTED]
    assert BriefStatus.DRAFT not in allowed


# ---------------------------------------------------------------------------
# New brand-portal workflow: full status flow
# ---------------------------------------------------------------------------


def test_submitted_can_go_to_accepted() -> None:
    """Brand submits → agency accepts."""
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.SUBMITTED]
    assert BriefStatus.ACCEPTED in allowed


def test_accepted_can_go_to_in_production() -> None:
    """Agency starts production after accepting."""
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.ACCEPTED]
    assert BriefStatus.IN_PRODUCTION in allowed


def test_in_production_can_go_to_ready_for_review() -> None:
    """Agency marks work ready for brand review."""
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.IN_PRODUCTION]
    assert BriefStatus.READY_FOR_REVIEW in allowed


def test_ready_for_review_can_go_to_approved() -> None:
    """Brand approves delivered work."""
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.READY_FOR_REVIEW]
    assert BriefStatus.APPROVED in allowed


def test_ready_for_review_can_go_to_revision_requested() -> None:
    """Brand can request revision on ready_for_review."""
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.READY_FOR_REVIEW]
    assert BriefStatus.REVISION_REQUESTED in allowed


def test_revision_requested_can_go_to_in_production() -> None:
    """Agency re-enters production after revision request."""
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.REVISION_REQUESTED]
    assert BriefStatus.IN_PRODUCTION in allowed


def test_approved_can_go_to_completed() -> None:
    """Approved brief can be completed."""
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.APPROVED]
    assert BriefStatus.COMPLETED in allowed


def test_approved_can_go_to_scheduled() -> None:
    """Approved brief can be scheduled on calendar."""
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.APPROVED]
    assert BriefStatus.SCHEDULED in allowed


def test_submitted_cannot_go_to_in_production_directly() -> None:
    """Cannot skip accepted step — agency must accept first."""
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.SUBMITTED]
    assert BriefStatus.IN_PRODUCTION not in allowed


def test_in_production_cannot_go_to_approved_directly() -> None:
    """Must pass through ready_for_review before approval."""
    from app.models.enums import BriefStatus
    from app.services.brief_service import _STATUS_TRANSITIONS

    allowed = _STATUS_TRANSITIONS[BriefStatus.IN_PRODUCTION]
    assert BriefStatus.APPROVED not in allowed


def test_brief_read_accepts_new_statuses() -> None:
    import uuid
    from datetime import datetime

    uid = uuid.uuid4()
    now = datetime.utcnow()
    for status in ("submitted", "in_production", "ready_for_review", "completed", "scheduled"):
        b = BriefRead(
            id=uid,
            agency_id=uid,
            brand_id=None,
            template_id=None,
            title="New Workflow Brief",
            description=None,
            status=status,
            priority="normal",
            deadline=None,
            source="brand_portal",
            meta=None,
            created_by_id=uid,
            updated_by_id=None,
            created_at=now,
            updated_at=now,
        )
        assert b.status == status


def test_brief_read_accepts_accepted_status() -> None:
    import uuid
    from datetime import datetime

    now = datetime.utcnow()
    uid = uuid.uuid4()
    b = BriefRead(
        id=uid,
        agency_id=uid,
        brand_id=None,
        template_id=None,
        title="Brand Request",
        description=None,
        status="accepted",
        priority="normal",
        deadline=None,
        source="brand_portal",
        meta={"platforms": ["instagram"]},
        created_by_id=uid,
        updated_by_id=None,
        created_at=now,
        updated_at=now,
    )
    assert b.status == "accepted"
    assert b.source == "brand_portal"

"""Unit tests for Brief Center and Brand Workspace dashboard schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.api.v1.dashboard import (
    AttentionItem,
    BrandBriefSummary,
    BrandCalendarItemSummary,
    BrandCardItem,
    BrandDeliverableSummary,
    BrandDNASummary,
    BrandKPI,
    BrandWorkspaceResponse,
    BriefCenterKPI,
    BriefCenterResponse,
)

# ── BriefCenterKPI ────────────────────────────────────────────────────────────


def test_brief_center_kpi_all_zero() -> None:
    kpi = BriefCenterKPI(
        total_active_briefs=0,
        overdue_briefs=0,
        revision_requested=0,
        pending_approvals=0,
        new_brand_requests=0,
        due_today=0,
    )
    assert kpi.total_active_briefs == 0
    assert kpi.due_today == 0


def test_brief_center_kpi_values() -> None:
    kpi = BriefCenterKPI(
        total_active_briefs=12,
        overdue_briefs=3,
        revision_requested=5,
        pending_approvals=2,
        new_brand_requests=1,
        due_today=4,
    )
    assert kpi.total_active_briefs == 12
    assert kpi.overdue_briefs == 3
    assert kpi.revision_requested == 5
    assert kpi.pending_approvals == 2
    assert kpi.new_brand_requests == 1
    assert kpi.due_today == 4


# ── AttentionItem ─────────────────────────────────────────────────────────────


def test_attention_item_overdue() -> None:
    item = AttentionItem(
        id=uuid.uuid4(),
        title="Nike Kampanya Brief",
        brand_id=uuid.uuid4(),
        brand_name="Nike",
        status="in_production",
        priority="high",
        deadline="2026-06-01",
        days_overdue=41,
        source="agency",
        attention_reason="overdue",
    )
    assert item.attention_reason == "overdue"
    assert item.days_overdue == 41
    assert item.brand_name == "Nike"


def test_attention_item_no_brand() -> None:
    item = AttentionItem(
        id=uuid.uuid4(),
        title="Genel Brief",
        brand_id=None,
        brand_name=None,
        status="draft",
        priority="urgent",
        deadline=None,
        days_overdue=None,
        source="agency",
        attention_reason="urgent",
    )
    assert item.brand_id is None
    assert item.brand_name is None
    assert item.days_overdue is None


def test_attention_item_revision_requested() -> None:
    item = AttentionItem(
        id=uuid.uuid4(),
        title="Logo Tasarım",
        brand_id=uuid.uuid4(),
        brand_name="Adidas",
        status="revision_requested",
        priority="normal",
        deadline="2026-08-01",
        days_overdue=None,
        source="brand_portal",
        attention_reason="revision_requested",
    )
    assert item.attention_reason == "revision_requested"
    assert item.source == "brand_portal"


# ── BrandCardItem ─────────────────────────────────────────────────────────────


def test_brand_card_item_all_zeros() -> None:
    card = BrandCardItem(
        id=uuid.uuid4(),
        name="Test Marka",
        logo_url=None,
        status="active",
        active_brief_count=0,
        overdue_count=0,
        revision_requested_count=0,
        pending_approval_count=0,
        this_week_calendar_count=0,
        last_activity_at=None,
        has_brand_dna=False,
        brand_dna_status=None,
    )
    assert card.active_brief_count == 0
    assert card.has_brand_dna is False
    assert card.brand_dna_status is None


def test_brand_card_item_with_dna() -> None:
    card = BrandCardItem(
        id=uuid.uuid4(),
        name="Nike",
        logo_url="/media/brand-logos/nike/logo.png",
        status="active",
        active_brief_count=5,
        overdue_count=2,
        revision_requested_count=1,
        pending_approval_count=3,
        this_week_calendar_count=4,
        last_activity_at="2026-07-10T14:30:00",
        has_brand_dna=True,
        brand_dna_status="approved",
    )
    assert card.has_brand_dna is True
    assert card.brand_dna_status == "approved"
    assert card.active_brief_count == 5
    assert card.overdue_count == 2


# ── BriefCenterResponse ───────────────────────────────────────────────────────


def test_brief_center_response_empty() -> None:
    kpis = BriefCenterKPI(
        total_active_briefs=0,
        overdue_briefs=0,
        revision_requested=0,
        pending_approvals=0,
        new_brand_requests=0,
        due_today=0,
    )
    resp = BriefCenterResponse(kpis=kpis, attention_items=[], brand_cards=[])
    assert resp.attention_items == []
    assert resp.brand_cards == []


def test_brief_center_response_with_items() -> None:
    kpis = BriefCenterKPI(
        total_active_briefs=3,
        overdue_briefs=1,
        revision_requested=0,
        pending_approvals=0,
        new_brand_requests=0,
        due_today=0,
    )
    item = AttentionItem(
        id=uuid.uuid4(),
        title="Brief X",
        brand_id=None,
        brand_name=None,
        status="in_production",
        priority="high",
        deadline="2026-07-01",
        days_overdue=11,
        source="agency",
        attention_reason="overdue",
    )
    card = BrandCardItem(
        id=uuid.uuid4(),
        name="Brand A",
        logo_url=None,
        status="active",
        active_brief_count=3,
        overdue_count=1,
        revision_requested_count=0,
        pending_approval_count=0,
        this_week_calendar_count=2,
        last_activity_at=None,
        has_brand_dna=False,
        brand_dna_status=None,
    )
    resp = BriefCenterResponse(kpis=kpis, attention_items=[item], brand_cards=[card])
    assert len(resp.attention_items) == 1
    assert len(resp.brand_cards) == 1
    assert resp.kpis.overdue_briefs == 1


# ── BrandKPI ──────────────────────────────────────────────────────────────────


def test_brand_kpi() -> None:
    kpi = BrandKPI(
        active_briefs=5,
        overdue_briefs=1,
        revision_requested=2,
        pending_approvals=3,
        this_week_calendar=4,
    )
    assert kpi.active_briefs == 5
    assert kpi.this_week_calendar == 4


# ── BrandBriefSummary ─────────────────────────────────────────────────────────


def test_brand_brief_summary() -> None:
    brief = BrandBriefSummary(
        id=uuid.uuid4(),
        title="Yaz Kampanyası",
        status="in_production",
        priority="high",
        deadline="2026-08-15",
        source="brand_portal",
        updated_at="2026-07-10T10:00:00",
    )
    assert brief.deadline == "2026-08-15"
    assert brief.source == "brand_portal"


def test_brand_brief_summary_no_deadline() -> None:
    brief = BrandBriefSummary(
        id=uuid.uuid4(),
        title="Belirsiz Brief",
        status="draft",
        priority="normal",
        deadline=None,
        source="agency",
        updated_at="2026-07-01T00:00:00",
    )
    assert brief.deadline is None


# ── BrandDeliverableSummary ───────────────────────────────────────────────────


def test_brand_deliverable_summary() -> None:
    d = BrandDeliverableSummary(
        id=uuid.uuid4(),
        brief_id=uuid.uuid4(),
        title="Banner Tasarım v2",
        deliverable_type="image",
        status="submitted",
        version_number=2,
        revision_count=1,
        updated_at="2026-07-08T12:00:00",
    )
    assert d.version_number == 2
    assert d.revision_count == 1
    assert d.deliverable_type == "image"


# ── BrandCalendarItemSummary ──────────────────────────────────────────────────


def test_brand_calendar_item_summary_with_dates() -> None:
    item = BrandCalendarItemSummary(
        id=uuid.uuid4(),
        title="Instagram Gönderisi",
        item_type="post",
        platform="instagram",
        status="planned",
        publish_at="2026-07-20T10:00:00",
        due_at="2026-07-19T17:00:00",
        brief_id=uuid.uuid4(),
    )
    assert item.publish_at == "2026-07-20T10:00:00"
    assert item.platform == "instagram"


def test_brand_calendar_item_summary_no_dates() -> None:
    item = BrandCalendarItemSummary(
        id=uuid.uuid4(),
        title="Genel İçerik",
        item_type="campaign",
        platform="other",
        status="planned",
        publish_at=None,
        due_at=None,
        brief_id=None,
    )
    assert item.publish_at is None
    assert item.due_at is None
    assert item.brief_id is None


# ── BrandDNASummary ───────────────────────────────────────────────────────────


def test_brand_dna_no_profile() -> None:
    dna = BrandDNASummary(
        has_profile=False,
        status=None,
        primary_colors=None,
        typography=None,
        tone_of_voice=None,
        summary=None,
    )
    assert dna.has_profile is False
    assert dna.primary_colors is None


def test_brand_dna_with_profile() -> None:
    dna = BrandDNASummary(
        has_profile=True,
        status="approved",
        primary_colors=["#FF0000", "#FFFFFF", "#000000"],
        typography=[{"family": "Inter", "weight": "600", "usage": "heading"}],
        tone_of_voice={"style": "professional", "personality": "bold"},
        summary="Nike is a global sportswear brand.",
    )
    assert dna.has_profile is True
    assert dna.status == "approved"
    assert len(dna.primary_colors) == 3  # type: ignore[arg-type]
    assert dna.tone_of_voice["style"] == "professional"


# ── BrandWorkspaceResponse ────────────────────────────────────────────────────


def test_brand_workspace_response() -> None:
    brand_id = uuid.uuid4()
    resp = BrandWorkspaceResponse(
        brand_id=brand_id,
        brand_name="Nike TR",
        brand_logo_url="/media/brand-logos/nike/logo.png",
        brand_status="active",
        kpis=BrandKPI(
            active_briefs=5,
            overdue_briefs=1,
            revision_requested=2,
            pending_approvals=0,
            this_week_calendar=3,
        ),
        recent_briefs=[],
        recent_deliverables=[],
        upcoming_calendar=[],
        brand_dna=BrandDNASummary(
            has_profile=True,
            status="ai_generated",
            primary_colors=["#FF0000"],
            typography=None,
            tone_of_voice=None,
            summary="Dinamik spor markası.",
        ),
    )
    assert resp.brand_id == brand_id
    assert resp.brand_name == "Nike TR"
    assert resp.kpis.active_briefs == 5
    assert resp.brand_dna.has_profile is True
    assert resp.recent_briefs == []


def test_brand_workspace_response_tenant_isolation() -> None:
    """Verify brand_id in workspace must be a valid UUID (tenant constraint enforced)."""
    with pytest.raises(ValidationError):
        BrandWorkspaceResponse(
            brand_id="not-a-uuid",  # type: ignore[arg-type]
            brand_name="Test",
            brand_logo_url=None,
            brand_status="active",
            kpis=BrandKPI(
                active_briefs=0,
                overdue_briefs=0,
                revision_requested=0,
                pending_approvals=0,
                this_week_calendar=0,
            ),
            recent_briefs=[],
            recent_deliverables=[],
            upcoming_calendar=[],
            brand_dna=BrandDNASummary(
                has_profile=False,
                status=None,
                primary_colors=None,
                typography=None,
                tone_of_voice=None,
                summary=None,
            ),
        )

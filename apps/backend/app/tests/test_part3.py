"""Part 3 tests: new notification events, BriefTask schemas, KPI dashboard schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.models.enums import NotificationEventType
from app.schemas.brief_task import BriefTaskCreate, BriefTaskRead, BriefTaskUpdate

# ── New notification event types ─────────────────────────────────────────────


def test_deliverable_submitted_event_type() -> None:
    assert NotificationEventType.DELIVERABLE_SUBMITTED == "deliverable.submitted"


def test_deliverable_approved_event_type() -> None:
    assert NotificationEventType.DELIVERABLE_APPROVED == "deliverable.approved"


def test_deliverable_revision_requested_event_type() -> None:
    assert NotificationEventType.DELIVERABLE_REVISION_REQUESTED == "deliverable.revision_requested"


def test_public_approval_approved_event_type() -> None:
    assert NotificationEventType.PUBLIC_APPROVAL_APPROVED == "public_approval.approved"


def test_public_approval_revision_requested_event_type() -> None:
    assert (
        NotificationEventType.PUBLIC_APPROVAL_REVISION_REQUESTED
        == "public_approval.revision_requested"
    )


def test_milestone_assigned_event_type() -> None:
    assert NotificationEventType.MILESTONE_ASSIGNED == "milestone.assigned"


# ── BriefTask schema validation ──────────────────────────────────────────────


def test_brief_task_create_minimal() -> None:
    t = BriefTaskCreate(title="Banner tasarımı yap")
    assert t.title == "Banner tasarımı yap"
    assert t.status == "todo"
    assert t.visibility == "internal"
    assert t.is_milestone is False


def test_brief_task_create_strips_title() -> None:
    t = BriefTaskCreate(title="  Görev başlığı  ")
    assert t.title == "Görev başlığı"


def test_brief_task_create_empty_title_raises() -> None:
    with pytest.raises(ValidationError):
        BriefTaskCreate(title="   ")


def test_brief_task_create_valid_statuses() -> None:
    for s in ("todo", "in_progress", "done", "blocked"):
        t = BriefTaskCreate(title="Görev", status=s)
        assert t.status == s


def test_brief_task_create_invalid_status_raises() -> None:
    with pytest.raises(ValidationError):
        BriefTaskCreate(title="Görev", status="pending")


def test_brief_task_create_valid_visibilities() -> None:
    for v in ("internal", "client_visible"):
        t = BriefTaskCreate(title="Görev", visibility=v)
        assert t.visibility == v


def test_brief_task_create_invalid_visibility_raises() -> None:
    with pytest.raises(ValidationError):
        BriefTaskCreate(title="Görev", visibility="public")


def test_brief_task_create_with_all_fields() -> None:
    uid = uuid.uuid4()
    t = BriefTaskCreate(
        title="Görsel üret",
        description="600x600 Instagram karesi",
        assigned_to_id=uid,
        due_date=date(2026, 8, 1),
        status="in_progress",
        visibility="client_visible",
        is_milestone=True,
    )
    assert t.assigned_to_id == uid
    assert t.due_date == date(2026, 8, 1)
    assert t.is_milestone is True


def test_brief_task_update_all_optional() -> None:
    u = BriefTaskUpdate()
    assert u.title is None
    assert u.status is None
    assert u.visibility is None


def test_brief_task_update_strips_title() -> None:
    u = BriefTaskUpdate(title="  Yeni başlık  ")
    assert u.title == "Yeni başlık"


def test_brief_task_update_invalid_status_raises() -> None:
    with pytest.raises(ValidationError):
        BriefTaskUpdate(status="invalid")


def test_brief_task_read_schema() -> None:
    now = datetime.now(UTC)
    uid = uuid.uuid4()
    r = BriefTaskRead(
        id=uid,
        agency_id=uid,
        brand_id=None,
        brief_id=uid,
        title="Test görev",
        description=None,
        assigned_to_id=None,
        due_date=None,
        status="todo",
        visibility="internal",
        created_by_id=uid,
        is_milestone=False,
        estimated_hours=None,
        created_at=now,
        updated_at=now,
    )
    assert r.status == "todo"
    assert r.is_milestone is False


def test_brief_task_model_importable() -> None:
    from app.models.brief_task import BriefTask

    assert BriefTask.__tablename__ == "brief_tasks"


def test_brief_task_model_in_init() -> None:
    from app.models import BriefTask

    assert BriefTask is not None


# ── WhatsApp template new methods ────────────────────────────────────────────


def test_whatsapp_deliverable_submitted_template() -> None:
    from app.services.whatsapp_template_service import whatsapp_templates

    msg = whatsapp_templates.deliverable_submitted(
        "Sosyal Medya Kampanyası",
        "Instagram Görseli",
        uuid.uuid4(),
    )
    assert "Teslimat" in msg
    assert "Instagram Görseli" in msg


def test_whatsapp_deliverable_approved_template() -> None:
    from app.services.whatsapp_template_service import whatsapp_templates

    msg = whatsapp_templates.deliverable_approved(
        "Brief Adı",
        "Video Reklam",
        uuid.uuid4(),
    )
    assert "Onaylandı" in msg


def test_whatsapp_deliverable_revision_template() -> None:
    from app.services.whatsapp_template_service import whatsapp_templates

    msg = whatsapp_templates.deliverable_revision_requested(
        "Brief",
        "Teslimat",
        uuid.uuid4(),
    )
    assert "Revizyon" in msg


def test_whatsapp_milestone_assigned_template() -> None:
    from app.services.whatsapp_template_service import whatsapp_templates

    msg = whatsapp_templates.milestone_assigned(
        "Banner tasarımı",
        "Marka Briefi",
        uuid.uuid4(),
    )
    assert "Görev" in msg
    assert "Banner tasarımı" in msg


# ── Email service generic with action_label ───────────────────────────────────


def test_email_generic_default_action_label() -> None:
    from app.services.email_service import build_generic_notification_html

    html = build_generic_notification_html(
        recipient_name="Test",
        title="Test",
        body="Test body",
        action_url="https://example.com",
    )
    assert "View" in html


def test_email_generic_turkish_action_label() -> None:
    from app.services.email_service import build_generic_notification_html

    html = build_generic_notification_html(
        recipient_name="Test",
        title="Test",
        body="Test body",
        action_url="https://example.com",
        locale="tr",
    )
    assert "Görüntüle" in html


def test_email_generic_custom_action_label() -> None:
    from app.services.email_service import build_generic_notification_html

    html = build_generic_notification_html(
        recipient_name="Test",
        title="Test",
        body="Test body",
        action_url="https://example.com",
        action_label="Teslimatı İncele",
    )
    assert "Teslimatı İncele" in html

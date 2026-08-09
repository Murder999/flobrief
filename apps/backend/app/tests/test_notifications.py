"""Unit tests for notification and activity log system.

No DB required — pure Python logic.
"""

from __future__ import annotations

from app.models.enums import (
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
)
from app.schemas.notification import NotificationPreferenceUpdate
from app.services.template_renderer import TemplateRenderer
from app.services.whatsapp_provider import PassiveWhatsAppProvider

# ── Enum value tests ──────────────────────────────────────────────────────────


def test_notification_channel_values() -> None:
    assert NotificationChannel.EMAIL == "email"
    assert NotificationChannel.WHATSAPP == "whatsapp"
    assert NotificationChannel.IN_APP == "in_app"


def test_notification_delivery_status_values() -> None:
    assert NotificationDeliveryStatus.PENDING == "pending"
    assert NotificationDeliveryStatus.SENT == "sent"
    assert NotificationDeliveryStatus.FAILED == "failed"
    assert NotificationDeliveryStatus.SKIPPED == "skipped"
    assert NotificationDeliveryStatus.PASSIVE == "passive"


def test_notification_event_type_values() -> None:
    assert NotificationEventType.BRIEF_CREATED == "brief.created"
    assert NotificationEventType.BRIEF_UPDATED == "brief.updated"
    assert NotificationEventType.BRIEF_SUBMITTED == "brief.submitted_for_approval"
    assert NotificationEventType.BRIEF_REVISION_REQUESTED == "brief.revision_requested"
    assert NotificationEventType.BRIEF_APPROVED == "brief.approved"
    assert NotificationEventType.BRIEF_REQUESTED == "brief.requested"
    assert NotificationEventType.COMMENT_ADDED == "comment.added"
    assert NotificationEventType.FILE_UPLOADED == "file.uploaded"
    assert NotificationEventType.CALENDAR_ITEM_CREATED == "calendar.item_created"
    assert NotificationEventType.CALENDAR_ITEM_DUE == "calendar.item_due"
    assert NotificationEventType.CALENDAR_ITEM_PUBLISHED == "calendar.item_published"
    assert NotificationEventType.USER_INVITED == "user.invited"
    assert NotificationEventType.SUBSCRIPTION_PAYMENT_FAILED == "subscription.payment_failed"
    assert NotificationEventType.SUBSCRIPTION_CHANGED == "subscription.changed"


def test_notification_event_type_count() -> None:
    # Part 2 Phase 7 added 10 capacity/finance event types (plan §14):
    # INVOICE_SENT, INVOICE_APPROVAL_PENDING, INVOICE_SEND_FAILED,
    # INVOICE_OVERDUE, TIME_OFF_APPROVED, TIME_OFF_REJECTED,
    # CAPACITY_OVER_THRESHOLD, COMMERCIAL_TERMS_EXPIRING, RETAINER_OVERAGE,
    # CRITICAL_WORK_UNASSIGNED.
    # Mention system added 2 more: MENTIONED_IN_COMMENT, MENTIONED_IN_ANNOTATION.
    # Part 6B-1 (WhatsApp event catalog) added 4 more: BRIEF_ASSIGNED,
    # BRIEF_OVERDUE, INVOICE_DUE_SOON, INVOICE_PAYMENT_RECEIVED.
    assert len(NotificationEventType) == 50


def test_notification_channel_count() -> None:
    assert len(NotificationChannel) == 3


def test_notification_delivery_status_count() -> None:
    # 7 original + 10 added for the Part 6A WhatsApp template-gated test-send flow
    # (queued, accepted, delivered, read, and 6 skipped_* reasons). Part 6B-2 added
    # 1 more: SKIPPED_EVENT_DISABLED (per-event WhatsApp toggle turned off). Part
    # 6B-3 added 3 more for the delivery state machine: CANCELLED, EXPIRED,
    # SKIPPED_ROLE (retry-time role re-validation).
    assert len(NotificationDeliveryStatus) == 21


# ── NotificationPreferenceUpdate validation ───────────────────────────────────


def test_preference_defaults() -> None:
    pref = NotificationPreferenceUpdate()
    assert pref.email_enabled is True
    assert pref.whatsapp_enabled is False
    assert pref.in_app_enabled is True


def test_preference_all_disabled() -> None:
    pref = NotificationPreferenceUpdate(
        email_enabled=False, whatsapp_enabled=False, in_app_enabled=False
    )
    assert pref.email_enabled is False
    assert pref.whatsapp_enabled is False
    assert pref.in_app_enabled is False


def test_preference_whatsapp_enabled() -> None:
    pref = NotificationPreferenceUpdate(whatsapp_enabled=True)
    assert pref.whatsapp_enabled is True


# ── TemplateRenderer tests ────────────────────────────────────────────────────


def test_template_render_basic() -> None:
    result = TemplateRenderer.render("Hello $name!", {"name": "Ahmet"})
    assert result == "Hello Ahmet!"


def test_template_render_multiple_vars() -> None:
    result = TemplateRenderer.render(
        "$agency - $brief", {"agency": "Test Ajans", "brief": "Kampanya"}
    )
    assert result == "Test Ajans - Kampanya"


def test_template_renderer_safe_xss() -> None:
    """HTML entities must be escaped to prevent XSS in email bodies."""
    result = TemplateRenderer.render(
        "<p>Merhaba $name</p>",
        {"name": '<script>alert("xss")</script>'},
    )
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_template_renderer_safe_html_entities() -> None:
    """Angle brackets, ampersands and quotes are escaped."""
    result = TemplateRenderer.render("$val", {"val": '<img src="x" onerror="alert(1)">'})
    assert "<img" not in result
    assert "&lt;img" in result


def test_template_render_missing_var_safe_substitute() -> None:
    """safe_substitute leaves unknown $var untouched instead of raising KeyError."""
    result = TemplateRenderer.render("Hello $name, you have $count messages.", {"name": "Ali"})
    assert "Ali" in result
    assert "$count" in result


def test_template_render_plain_no_escape() -> None:
    plain = TemplateRenderer.render_plain("Hello $name", {"name": "Test & Co"})
    assert plain == "Hello Test & Co"


# ── PassiveWhatsAppProvider tests ─────────────────────────────────────────────


def test_passive_whatsapp_not_configured_by_default() -> None:
    provider = PassiveWhatsAppProvider()
    assert provider.validate_config() is False


def test_passive_whatsapp_send_returns_passive_status() -> None:
    provider = PassiveWhatsAppProvider()
    result = provider.send(to_phone="+905551234567", template_body="Test mesajı")
    assert result.status == "not_configured"
    assert result.provider == "disabled"


def test_passive_whatsapp_send_no_external_call() -> None:
    """PassiveWhatsAppProvider must not raise or call external APIs — side-effect-free."""
    import socket

    original_getaddrinfo = socket.getaddrinfo

    called: list[str] = []

    def spy_getaddrinfo(host: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        if "graph.facebook.com" in host or "api.whatsapp.com" in host:
            called.append(host)
        return original_getaddrinfo(host, *args, **kwargs)

    socket.getaddrinfo = spy_getaddrinfo
    try:
        provider = PassiveWhatsAppProvider()
        provider.send(to_phone="+905551234567", template_body="Passive test")
    finally:
        socket.getaddrinfo = original_getaddrinfo

    assert len(called) == 0, f"External host was called: {called}"


def test_passive_whatsapp_send_has_error_message() -> None:
    provider = PassiveWhatsAppProvider()
    result = provider.send(to_phone="+905551234567", template_body="msg")
    assert result.error_message is not None
    assert len(result.error_message) > 10


def test_passive_whatsapp_skipped_result() -> None:
    provider = PassiveWhatsAppProvider()
    result = provider.skipped()
    assert result.status == "skipped"
    assert result.provider == "disabled"


def test_passive_whatsapp_no_provider_message_id() -> None:
    provider = PassiveWhatsAppProvider()
    result = provider.send(to_phone="+905551234567", template_body="msg")
    assert result.provider_message_id is None


# ── Notification event types cover all flows ──────────────────────────────────


def test_brief_event_types_complete() -> None:
    # Part 6B-1 added BRIEF_ASSIGNED and BRIEF_OVERDUE (WhatsApp event catalog).
    brief_events = [e for e in NotificationEventType if e.value.startswith("brief.")]
    assert len(brief_events) == 14


def test_calendar_event_types_complete() -> None:
    cal_events = [e for e in NotificationEventType if e.value.startswith("calendar.")]
    assert len(cal_events) == 3


def test_subscription_event_types_complete() -> None:
    sub_events = [e for e in NotificationEventType if e.value.startswith("subscription.")]
    assert len(sub_events) == 2


# ── Tenant isolation: brand users have no agency_view (conceptual test) ───────


def test_notification_event_type_uses_dot_notation() -> None:
    """Event types use dot notation (domain.action) for future webhook compatibility."""
    for event_type in NotificationEventType:
        assert "." in event_type.value, f"{event_type.value!r} missing dot notation"


def test_delivery_statuses_cover_whatsapp_passive_states() -> None:
    statuses = {s.value for s in NotificationDeliveryStatus}
    assert "passive" in statuses
    assert "skipped" in statuses
    assert "sent" in statuses
    assert "failed" in statuses

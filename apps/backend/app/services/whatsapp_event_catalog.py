"""Typed WhatsApp event catalog (Part 6B-1).

Single source of truth mapping a `NotificationEventType` to the WhatsApp
`template_key` used to look it up in the `whatsapp_templates` registry
(`WhatsAppTemplateRepository.get_approved`). Nothing here talks to Twilio —
this module only describes *which* approved template a domain event maps to.
The actual variable payload is built by `whatsapp_payload_builder`, and
WhatsApp-only recipient narrowing (beyond what the domain service already
resolved) lives in `whatsapp_recipient_gate`. Deduplication is handled by the
dispatcher keying each delivery's `idempotency_key` off the immutable
`NotificationEvent.id` + recipient + channel (see notification_dispatcher.py)
— never off payload fields, which differ in shape per event and would risk
collapsing two distinct real actions (e.g. two different annotation replies)
into a single "duplicate".

A template_key here is never reused as a raw string elsewhere — always go
through `WHATSAPP_EVENT_CATALOG[event_type].template_key`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import NotificationEventType


@dataclass(frozen=True)
class WhatsAppEventDefinition:
    """Static metadata for one WhatsApp-eligible domain event."""

    event_type: str
    template_key: str
    # Short human description of who should receive this event on WhatsApp —
    # enforcement of the interesting cases (role narrowing) lives in
    # whatsapp_recipient_gate; this field documents intent for reviewers.
    recipient_policy: str
    locale_fallback: str = "tr"


WHATSAPP_EVENT_CATALOG: dict[str, WhatsAppEventDefinition] = {
    NotificationEventType.BRIEF_CREATED.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.BRIEF_CREATED.value,
        template_key="brief_created",
        recipient_policy="Agency members assigned/visible to the brief's brand.",
    ),
    NotificationEventType.BRIEF_ASSIGNED.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.BRIEF_ASSIGNED.value,
        template_key="brief_assigned",
        recipient_policy="Only the newly-added assignee, never the whole team.",
    ),
    NotificationEventType.COMMENT_ADDED.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.COMMENT_ADDED.value,
        template_key="comment_added",
        recipient_policy="Agency members + (client_visible only) brand members, minus actor.",
    ),
    NotificationEventType.MENTIONED_IN_COMMENT.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.MENTIONED_IN_COMMENT.value,
        template_key="mention_created",
        recipient_policy="Only users actually @mentioned in this comment (MentionService).",
    ),
    NotificationEventType.MENTIONED_IN_ANNOTATION.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.MENTIONED_IN_ANNOTATION.value,
        template_key="mention_created",
        recipient_policy="Only users actually @mentioned in this annotation (MentionService).",
    ),
    NotificationEventType.DELIVERABLE_SUBMITTED.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.DELIVERABLE_SUBMITTED.value,
        template_key="deliverable_submitted",
        recipient_policy="Brand members of the deliverable's brand.",
    ),
    NotificationEventType.BRIEF_SUBMITTED.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.BRIEF_SUBMITTED.value,
        template_key="approval_requested",
        recipient_policy=(
            "Brand members holding brief:approve — narrowed in whatsapp_recipient_gate."
        ),
    ),
    NotificationEventType.DELIVERABLE_APPROVED.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.DELIVERABLE_APPROVED.value,
        template_key="deliverable_approved",
        recipient_policy="Agency members of the deliverable's agency.",
    ),
    NotificationEventType.BRIEF_REVISION_REQUESTED.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.BRIEF_REVISION_REQUESTED.value,
        template_key="revision_requested",
        recipient_policy="Agency members of the brief's agency.",
    ),
    NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value,
        template_key="revision_requested",
        recipient_policy="Agency members of the deliverable's agency.",
    ),
    NotificationEventType.ANNOTATION_CREATED.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.ANNOTATION_CREATED.value,
        template_key="annotation_created",
        recipient_policy="Agency/brand members with access to the deliverable, minus actor.",
    ),
    NotificationEventType.ANNOTATION_REPLIED.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.ANNOTATION_REPLIED.value,
        template_key="annotation_replied",
        recipient_policy="Annotation thread participants, minus actor.",
    ),
    NotificationEventType.CALENDAR_ITEM_DUE.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.CALENDAR_ITEM_DUE.value,
        template_key="brief_due_soon",
        recipient_policy="Agency members of the brief's agency (deadline_scheduler).",
    ),
    NotificationEventType.BRIEF_OVERDUE.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.BRIEF_OVERDUE.value,
        template_key="brief_overdue",
        recipient_policy="Agency members of the brief's agency (deadline_scheduler).",
    ),
    NotificationEventType.INVOICE_SENT.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.INVOICE_SENT.value,
        template_key="invoice_sent",
        recipient_policy="Brand members of the invoiced brand (the client), never agency staff.",
    ),
    NotificationEventType.INVOICE_DUE_SOON.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.INVOICE_DUE_SOON.value,
        template_key="invoice_due_soon",
        recipient_policy="Brand members of the invoiced brand (the client).",
    ),
    NotificationEventType.INVOICE_OVERDUE.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.INVOICE_OVERDUE.value,
        template_key="invoice_overdue",
        recipient_policy="Agency members holding invoice:approve — never the brand.",
    ),
    NotificationEventType.INVOICE_PAYMENT_RECEIVED.value: WhatsAppEventDefinition(
        event_type=NotificationEventType.INVOICE_PAYMENT_RECEIVED.value,
        template_key="invoice_payment_received",
        recipient_policy=(
            "Agency members holding invoice:view — narrowed in whatsapp_recipient_gate."
        ),
    ),
}


def get_event_definition(event_type: str) -> WhatsAppEventDefinition | None:
    """Return the catalog entry for a domain event type, or None if this
    event has no WhatsApp channel at all (e.g. internal/system events)."""
    return WHATSAPP_EVENT_CATALOG.get(event_type)


__all__ = ["WhatsAppEventDefinition", "WHATSAPP_EVENT_CATALOG", "get_event_definition"]

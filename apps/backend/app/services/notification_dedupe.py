"""Domain-level idempotency key for WhatsApp deliveries (Part 6B-1 closing).

`NotificationDispatcher._dispatch_whatsapp` used to key `idempotency_key`
off `NotificationEvent.id` alone. That prevents the exact same
`NotificationEvent` row from ever being re-dispatched twice, but it does
nothing when the *same real domain occurrence* (the same comment, the same
deliverable submission, the same due-soon reminder for the same brief on
the same day, ...) is emitted as two separate `NotificationEvent` rows —
e.g. a duplicated `emit()` call, an at-least-once redelivery, or two
scheduler runs racing on the same day. This module derives the key from the
domain occurrence itself, using only fields already present on
`NotificationEvent.payload` at each `emit()` call site — never from
`NotificationEvent.id`.
"""

from __future__ import annotations

import hashlib
import uuid

from app.core.time_utils import utc_today
from app.models.enums import NotificationEventType
from app.models.notification import NotificationEvent

# Reminder-style events re-fire once per day per entity — deadline_scheduler
# and finance_capacity_scheduler already coarsely dedupe *event creation*
# within a ~23h window; bucketing by the current UTC day here means a
# legitimate next-day reminder is never swallowed.
_DAILY_BRIEF_REMINDER_EVENTS = frozenset(
    {
        NotificationEventType.CALENDAR_ITEM_DUE.value,
        NotificationEventType.BRIEF_OVERDUE.value,
    }
)
_DAILY_INVOICE_REMINDER_EVENTS = frozenset(
    {
        NotificationEventType.INVOICE_DUE_SOON.value,
        NotificationEventType.INVOICE_OVERDUE.value,
    }
)
# deliverable_versioning.py: "a revision request mutates the same row in
# place ... rather than creating a new historical row" — so for these two
# events the same deliverable_id is reused across resubmissions, and
# `revision_count` (bumped once per real revision request, see
# brand_portal.py's request-revision handler) is what actually distinguishes
# one real occurrence from the next.
_DELIVERABLE_REVISION_SCOPED_EVENTS = frozenset(
    {
        NotificationEventType.DELIVERABLE_SUBMITTED.value,
        NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value,
    }
)
_ANNOTATION_SCOPED_EVENTS = frozenset(
    {
        NotificationEventType.ANNOTATION_CREATED.value,
        NotificationEventType.ANNOTATION_REPLIED.value,
        NotificationEventType.ANNOTATION_RESOLVED.value,
        NotificationEventType.ANNOTATION_REOPENED.value,
    }
)
_COMMENT_SCOPED_EVENTS = frozenset(
    {
        NotificationEventType.COMMENT_ADDED.value,
        NotificationEventType.MENTIONED_IN_COMMENT.value,
    }
)


def _domain_occurrence_key(event: NotificationEvent) -> str:
    """A string that is identical for two `NotificationEvent` rows
    representing the same real domain action, and different for two rows
    representing genuinely distinct actions. Built only from fields already
    on `event.payload` — never from `event.id`."""
    p = event.payload
    et = event.event_type

    if et in _DAILY_BRIEF_REMINDER_EVENTS:
        return f"brief={p.get('brief_id', '')}:day={utc_today().isoformat()}"
    if et in _DAILY_INVOICE_REMINDER_EVENTS:
        return f"invoice={p.get('invoice_id', '')}:day={utc_today().isoformat()}"
    if et == NotificationEventType.INVOICE_PAYMENT_RECEIVED.value:
        return f"payment={p.get('payment_id', '')}"
    if et == NotificationEventType.INVOICE_SENT.value:
        return f"invoice={p.get('invoice_id', '')}"
    if et in _COMMENT_SCOPED_EVENTS:
        return f"comment={p.get('comment_id', '')}"
    if et == NotificationEventType.MENTIONED_IN_ANNOTATION.value:
        return f"annotation={p.get('annotation_id', '')}"
    if et in _DELIVERABLE_REVISION_SCOPED_EVENTS:
        return f"deliverable={p.get('deliverable_id', '')}:revision={p.get('revision_count', 0)}"
    if et in _ANNOTATION_SCOPED_EVENTS:
        return f"annotation={p.get('annotation_id', '')}"
    if et == NotificationEventType.BRIEF_ASSIGNED.value:
        return f"brief={p.get('brief_id', '')}:assignee={p.get('assignee_id', '')}"
    if et == NotificationEventType.DELIVERABLE_APPROVED.value:
        return f"deliverable={p.get('deliverable_id', '')}"
    if "dedup_key" in p:
        # finance_capacity_scheduler already computes a precise per-period
        # dedup_key for scan-based events with no single natural entity id
        # (capacity.over_threshold, commercial_terms.expiring,
        # capacity.critical_work_unassigned) — reuse it verbatim.
        return f"dedup={p['dedup_key']}"
    # Remaining brief-status-transition broadcasts (brief.created,
    # brief.accepted, brief.production_started, brief.ready_for_review,
    # brief.approved, brief.completed, brief.submitted,
    # brief.revision_requested): brief_service.py stamps a `status_version`
    # (the brief's own `updated_at` at transition time, already bumped by
    # that same transition) onto each of these payloads specifically so two
    # genuinely separate transitions to the same status (e.g. two different
    # revision-request cycles) are never collapsed into one message, while
    # an exact duplicate emit of one transition is.
    entity = p.get("brief_id") or p.get("deliverable_id") or p.get("invoice_id") or ""
    return f"entity={entity}:version={p.get('status_version', '')}"


def build_whatsapp_idempotency_key(event: NotificationEvent, recipient_user_id: uuid.UUID) -> str:
    """Deterministic WhatsApp delivery idempotency key for one (domain
    occurrence, recipient) pair. Independent of `NotificationEvent.id`, so
    two `NotificationEvent` rows created for the same real action collapse
    to the same key. The components are hashed (not stored raw) so the
    result comfortably fits the `idempotency_key` column
    (`String(100)`) regardless of entity id / event_type length, with
    negligible collision risk (sha256, 64 hex chars)."""
    raw = f"{event.event_type}:{_domain_occurrence_key(event)}:{recipient_user_id}:whatsapp"
    return "wa:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


__all__ = ["build_whatsapp_idempotency_key"]

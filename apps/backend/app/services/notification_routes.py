"""Computes safe, relative in-app deep-link routes for notifications.

Routes are built entirely server-side from trusted event payload fields (UUIDs
minted by our own code, never raw user input), and are always relative paths
rooted at /dashboard or /brand. The frontend must never construct or accept an
arbitrary user-controlled URL here — this module is the single source of truth
for "where does this notification go".
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal
from urllib.parse import urlencode

from app.models.enums import NotificationEventType

Portal = Literal["agency", "brand"]

# Recipients of these three are always the individual agency member the
# event is about (the timer's owner, or the person missing their own
# timesheet) — never a manager. Routing them anywhere team-scoped
# (/dashboard/time/team, /by-brand, /missing) would 403 for anyone without
# TIME_ENTRY_VIEW_TEAM, so all three land on the self-service "my time"
# view, which every workspace member can open regardless of role.
_TIMER_EVENTS = {
    NotificationEventType.TIME_ENTRY_LONG_RUNNING.value,
    NotificationEventType.TIME_ENTRY_STILL_RUNNING_EOD.value,
}
_TIMESHEET_MISSING_EVENTS = {NotificationEventType.TIMESHEET_MISSING.value}

# ClientInvoice-scoped events — routed by invoice_id, not brief_id (a
# ClientInvoice has no brief_id at all). INVOICE_SENT's recipients are the
# brand's own portal users (see ClientInvoiceService.send); the other three
# (approval-pending/send-failed/overdue) are agency-internal, dispatched to
# holders of INVOICE_APPROVE/ACCOUNTING_INTEGRATION_MANAGE-adjacent
# permissions — never sent to a brand session, but this function stays
# defensive rather than emit an agency-only path for a brand portal.
_INVOICE_EVENTS = {
    NotificationEventType.INVOICE_SENT.value,
    NotificationEventType.INVOICE_APPROVAL_PENDING.value,
    NotificationEventType.INVOICE_SEND_FAILED.value,
    NotificationEventType.INVOICE_OVERDUE.value,
}

_DELIVERABLE_EVENTS = {
    NotificationEventType.DELIVERABLE_SUBMITTED.value,
    NotificationEventType.DELIVERABLE_APPROVED.value,
    NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value,
    NotificationEventType.ANNOTATION_CREATED.value,
    NotificationEventType.ANNOTATION_RESOLVED.value,
    NotificationEventType.ANNOTATION_REPLIED.value,
    NotificationEventType.ANNOTATION_REOPENED.value,
}

_COMMENT_EVENTS = {
    NotificationEventType.COMMENT_ADDED.value,
    NotificationEventType.MENTIONED_IN_COMMENT.value,
}

_MENTION_ANNOTATION_EVENTS = {NotificationEventType.MENTIONED_IN_ANNOTATION.value}

_BRIEF_LEVEL_EVENTS = {
    NotificationEventType.BRIEF_CREATED.value,
    NotificationEventType.BRIEF_UPDATED.value,
    NotificationEventType.BRIEF_SUBMITTED.value,
    NotificationEventType.BRIEF_REQUESTED.value,
    NotificationEventType.BRIEF_ACCEPTED.value,
    NotificationEventType.BRIEF_PRODUCTION_STARTED.value,
    NotificationEventType.BRIEF_READY_FOR_REVIEW.value,
    NotificationEventType.BRIEF_REVISION_REQUESTED.value,
    NotificationEventType.BRIEF_APPROVED.value,
    NotificationEventType.BRIEF_REJECTED.value,
    NotificationEventType.BRIEF_COMPLETED.value,
    NotificationEventType.FILE_UPLOADED.value,
    NotificationEventType.PUBLIC_APPROVAL_APPROVED.value,
    NotificationEventType.PUBLIC_APPROVAL_REVISION_REQUESTED.value,
    NotificationEventType.MILESTONE_ASSIGNED.value,
    NotificationEventType.BRIEF_ESTIMATE_OVERRUN.value,
}


def _safe_uuid_str(value: object) -> str | None:
    """Only ever returns a canonical UUID string, never a raw pass-through."""
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _safe_iso_date_str(value: object) -> str | None:
    """Only ever returns a canonical YYYY-MM-DD string, never a raw pass-through."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def build_notification_action_url(
    event_type: str,
    payload: dict,
    portal: Portal,
) -> str | None:
    """Compute a relative in-app route for a notification, or None if unroutable.

    None means the frontend shows a safe fallback (the notifications list)
    instead of navigating — this happens for legacy events with no brief_id,
    or event types this function doesn't yet recognize.
    """
    if event_type in _TIMER_EVENTS:
        # Brand users never see time-tracking notifications (recipients are
        # always agency members), but stay defensive: unroutable rather
        # than pointing a brand session at an agency-only path.
        return "/dashboard/time/my?timer=active" if portal == "agency" else None

    if event_type in _TIMESHEET_MISSING_EVENTS:
        if portal != "agency":
            return None
        missing_date = _safe_iso_date_str(payload.get("missing_date"))
        if not missing_date:
            return "/dashboard/time/my"
        params = {"range": "custom", "start": missing_date, "end": missing_date}
        return f"/dashboard/time/my?{urlencode(params)}"

    if event_type in _INVOICE_EVENTS:
        invoice_id = _safe_uuid_str(payload.get("invoice_id"))
        if not invoice_id:
            return None
        return (
            f"/brand/invoices/{invoice_id}"
            if portal == "brand"
            else f"/dashboard/finance/invoices/{invoice_id}"
        )

    brief_id = _safe_uuid_str(payload.get("brief_id"))
    if not brief_id:
        return None

    base = f"/dashboard/briefs/{brief_id}" if portal == "agency" else f"/brand/briefs/{brief_id}"

    if event_type in _DELIVERABLE_EVENTS:
        params: dict[str, str] = (
            {"tab": "uretim"} if portal == "agency" else {"section": "deliverables"}
        )
        deliverable_id = _safe_uuid_str(payload.get("deliverable_id"))
        annotation_id = _safe_uuid_str(payload.get("annotation_id"))
        if deliverable_id:
            params["deliverable"] = deliverable_id
        if annotation_id:
            params["annotation"] = annotation_id
        return f"{base}?{urlencode(params)}"

    if event_type in _COMMENT_EVENTS:
        params = {"panel": "comments"}
        comment_id = _safe_uuid_str(payload.get("comment_id"))
        if comment_id:
            params["comment"] = comment_id
        return f"{base}?{urlencode(params)}"

    if event_type in _MENTION_ANNOTATION_EVENTS:
        params = {"tab": "uretim"} if portal == "agency" else {"section": "deliverables"}
        deliverable_id = _safe_uuid_str(payload.get("deliverable_id"))
        annotation_id = _safe_uuid_str(payload.get("annotation_id"))
        if deliverable_id:
            params["deliverable"] = deliverable_id
        if annotation_id:
            params["annotation"] = annotation_id
        return f"{base}?{urlencode(params)}"

    if event_type in _BRIEF_LEVEL_EVENTS:
        return base

    return None

"""Safe, allowlist-based WhatsApp template variable builder (Part 6B-1).

Nothing here ever emits a full comment/annotation/revision body, an internal
cost/rate figure, a credential, or a raw phone/email — only the fields in
`ALLOWED_VARIABLE_FIELDS` can ever reach a Twilio ContentVariables payload,
and free-text fields (comment previews, revision reasons) are always routed
through `short_safe_preview()` first: HTML stripped, whitespace collapsed,
hard-truncated. The caller (a user) never controls a template variable name —
only `WhatsAppTemplate.variable_schema` (operator-configured, DB-stored) picks
which allowed field lands on which Twilio `{{n}}` placeholder.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime

from app.models.enums import NotificationEventType, UserType
from app.models.notification import NotificationEvent
from app.models.template import WhatsAppTemplate
from app.models.user import User
from app.services.url_builder import url_builder

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_SHORT_SUMMARY_LIMIT = 80

# The only variable names a WhatsApp template body may ever reference.
# WhatsAppTemplate.variable_schema maps Twilio placeholder numbers ("1", "2",
# ...) to one of these — anything else is dropped, never sent.
ALLOWED_VARIABLE_FIELDS: frozenset[str] = frozenset(
    {
        "recipient_first_name",
        "actor_display_name",
        "brief_title",
        "brand_name",
        "deliverable_title",
        "due_date",
        "invoice_number",
        "invoice_total_formatted",
        "short_safe_summary",
        "deep_link_url",
    }
)

_COMMENT_LIKE_EVENTS = frozenset(
    {
        NotificationEventType.COMMENT_ADDED.value,
        NotificationEventType.MENTIONED_IN_COMMENT.value,
    }
)


def _first_name(full_name: str | None) -> str:
    if not full_name:
        return ""
    return full_name.strip().split(" ")[0]


def strip_to_plain_text(value: str | None) -> str:
    """Strip HTML tags and collapse whitespace/newlines. Never raises."""
    if not value:
        return ""
    without_tags = _TAG_RE.sub(" ", value)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def short_safe_preview(value: str | None, *, limit: int = _SHORT_SUMMARY_LIMIT) -> str:
    """Plain-text, whitespace-collapsed, hard-truncated preview.

    Always the last transformation applied to any free-text field (comment
    preview, revision reason, activity summary) before it can become a
    template variable — never the raw/full value."""
    text = strip_to_plain_text(value)
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _format_due_date(raw: object) -> str:
    if not raw:
        return "—"
    if isinstance(raw, date | datetime):
        return raw.strftime("%d.%m.%Y")
    try:
        parsed = datetime.fromisoformat(str(raw))
    except ValueError:
        return str(raw)[:10]
    return parsed.strftime("%d.%m.%Y")


def _format_money(cents: object, currency: object) -> str:
    if not isinstance(cents, int):
        return ""
    amount = cents / 100
    grouped = f"{amount:,.2f}"
    # en-US grouping ("1,234.56") -> tr-TR grouping ("1.234,56")
    tr_amount = grouped.replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{tr_amount} {currency or 'TRY'}"


def _is_brand_recipient(recipient: User) -> bool:
    return recipient.user_type == UserType.BRAND_USER.value


def _uuid_from_payload(payload: dict, key: str) -> uuid.UUID | None:
    raw = payload.get(key)
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


def resolve_deep_link(event: NotificationEvent, recipient: User) -> str:
    """Build the action URL for this event/recipient pair.

    Never derived from request input — only from server-resolved entity IDs
    already stored on the NotificationEvent payload, routed through
    UrlBuilder (FRONTEND_PUBLIC_URL). Picks the agency or brand portal path
    based on the recipient's own account type, so the link always lands
    behind that recipient's normal permission check."""
    p = event.payload
    brand_side = _is_brand_recipient(recipient)
    brief_id = _uuid_from_payload(p, "brief_id")
    deliverable_id = _uuid_from_payload(p, "deliverable_id")
    annotation_id = _uuid_from_payload(p, "annotation_id")
    invoice_id = _uuid_from_payload(p, "invoice_id")

    if invoice_id is not None:
        return url_builder.invoice_detail(invoice_id, brand_side=brand_side)
    if annotation_id is not None and deliverable_id is not None and brief_id is not None:
        return url_builder.annotation_detail(
            brief_id, deliverable_id, annotation_id, brand_side=brand_side
        )
    if deliverable_id is not None and brief_id is not None:
        return url_builder.deliverable_detail(brief_id, deliverable_id, brand_side=brand_side)
    if event.event_type in _COMMENT_LIKE_EVENTS and brief_id is not None:
        return url_builder.brief_comments(brief_id, brand_side=brand_side)
    if brief_id is not None:
        return (
            url_builder.brand_brief_detail(brief_id)
            if brand_side
            else url_builder.brief_detail(brief_id)
        )
    return url_builder.notification_preferences(brand_side=brand_side)


def _short_safe_summary_for(event: NotificationEvent) -> str:
    """Picks the least-sensitive available free-text source for this event
    and always routes it through short_safe_preview(). Comment/annotation/
    revision bodies themselves are never in the payload to begin with (the
    domain services only ever store short previews/reasons there) — this is
    an extra truncation/HTML-strip pass, not the only safeguard."""
    p = event.payload
    source = p.get("comment_preview") or p.get("reason") or p.get("summary")
    return short_safe_preview(source)


def build_variables(
    event: NotificationEvent,
    recipient: User,
    actor: User | None = None,
) -> dict[str, str]:
    """Build the full allowlisted variable set for this event/recipient.

    Returns only keys in ALLOWED_VARIABLE_FIELDS. A template that needs a
    field with no derivable value here simply gets an empty string for it —
    callers decide via WhatsAppTemplate.variable_schema which of these
    actually get used."""
    p = event.payload
    actor_name = p.get("actor_name") or (actor.full_name if actor else "") or ""

    variables: dict[str, str] = {
        "recipient_first_name": _first_name(recipient.full_name),
        "actor_display_name": actor_name,
        "brief_title": str(p.get("brief_title") or ""),
        "brand_name": str(p.get("brand_name") or p.get("agency_name") or ""),
        "deliverable_title": str(p.get("deliverable_title") or ""),
        "due_date": _format_due_date(p.get("due_date") or p.get("deadline")),
        "invoice_number": str(p.get("invoice_number") or ""),
        "invoice_total_formatted": _format_money(p.get("amount_cents"), p.get("currency")),
        "short_safe_summary": _short_safe_summary_for(event),
        "deep_link_url": resolve_deep_link(event, recipient),
    }
    return variables


def map_to_content_variables(
    template: WhatsAppTemplate, variables: dict[str, str]
) -> dict[str, str]:
    """Translate the semantic allowlisted `variables` dict into the Twilio
    ContentVariables shape (`{"1": "...", "2": "..."}`) using the approved
    template's `variable_schema` (`{"1": "brief_title", ...}`). Any schema
    entry naming a field outside ALLOWED_VARIABLE_FIELDS is dropped — schema
    rows are operator-authored, but this keeps the allowlist authoritative
    even if a schema row is misconfigured."""
    content_variables: dict[str, str] = {}
    for placeholder, field_name in (template.variable_schema or {}).items():
        if field_name not in ALLOWED_VARIABLE_FIELDS:
            continue
        content_variables[str(placeholder)] = variables.get(field_name, "")
    return content_variables


__all__ = [
    "ALLOWED_VARIABLE_FIELDS",
    "strip_to_plain_text",
    "short_safe_preview",
    "resolve_deep_link",
    "build_variables",
    "map_to_content_variables",
]

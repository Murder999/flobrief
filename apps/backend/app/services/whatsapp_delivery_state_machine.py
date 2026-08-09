"""Monotonic delivery-status state machine for WhatsApp `NotificationDelivery`
rows (Part 6B-3).

Scope: this module governs transitions driven by *provider callbacks*
(Twilio status webhook) — duplicate delivery, out-of-order delivery, and
never-regress guarantees for the queued → accepted → sent → delivered →
read progress path plus its terminal failure/skip/cancel states.

It is deliberately NOT used by the retry worker's own attempt bookkeeping
(scheduling a next attempt, exhausting retries, cancelling a pending retry
on opt-out) — those are forward-looking application decisions about a *new*
attempt on the same row, not a report of what already happened, and they are
allowed to move a row out of the terminal FAILED state on purpose. Mixing
the two into one generic validator would either block legitimate retries or
weaken the guarantee this module gives callback processing. See
whatsapp_retry_worker.py / NotificationDeliveryRepository's retry methods
for that side.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import NotificationDeliveryStatus as S
from app.models.notification import NotificationDelivery

# Forward progress ranks. Only PROCESSING..READ participate in monotonic
# ordering; anything not listed here is a terminal status (see
# _TERMINAL_STATUSES) reachable from any non-terminal rank but never a
# source of further transitions.
_PROGRESS_RANK: dict[str, int] = {
    S.PROCESSING.value: -1,
    S.PENDING.value: 0,
    S.QUEUED.value: 1,
    S.ACCEPTED.value: 2,
    S.SENT.value: 3,
    S.DELIVERED.value: 4,
    S.READ.value: 5,
}

# Every status that, once reached, accepts no further transition through
# this module. READ is progress-path terminal (rank 5, nothing after it);
# the rest are failure/skip/cancel outcomes reachable from any non-terminal
# progress state.
_TERMINAL_FAILURE_STATUSES: frozenset[str] = frozenset(
    {
        S.FAILED.value,
        S.CANCELLED.value,
        S.EXPIRED.value,
        S.SKIPPED.value,
        S.SKIPPED_ROLE.value,
        S.SKIPPED_DISABLED.value,
        S.SKIPPED_NO_CONSENT.value,
        S.SKIPPED_NO_PHONE.value,
        S.SKIPPED_UNVERIFIED_PHONE.value,
        S.SKIPPED_TEMPLATE_MISSING.value,
        S.SKIPPED_DEMO_TENANT.value,
        S.SKIPPED_EVENT_DISABLED.value,
        S.NOT_CONFIGURED.value,
        S.PASSIVE.value,
    }
)

_TIMESTAMP_FIELD_FOR_STATUS: dict[str, str] = {
    S.QUEUED.value: "queued_at",
    S.ACCEPTED.value: "accepted_at",
    S.SENT.value: "sent_at",
    S.DELIVERED.value: "delivered_at",
    S.READ.value: "read_at",
    S.FAILED.value: "failed_at",
    S.CANCELLED.value: "cancelled_at",
    S.EXPIRED.value: "expired_at",
}


def is_terminal(status: str) -> bool:
    """True for any status that no longer accepts callback-driven
    transitions — every failure/skip/cancel/expire outcome, plus READ."""
    return status in _TERMINAL_FAILURE_STATUSES or status == S.READ.value


def rank(status: str) -> int | None:
    """Progress-path rank, or None for a status outside the progress path
    (i.e. a terminal failure/skip status, or an unrecognized value)."""
    return _PROGRESS_RANK.get(status)


@dataclass(frozen=True)
class TransitionResult:
    """Outcome of one `apply_transition` call. `applied=False` is not an
    error — it covers duplicate callbacks (same status reported twice) and
    out-of-order/regressive callbacks (an earlier-stage status arriving
    after a later one already landed), both of which must be silently
    absorbed rather than mutate the row."""

    applied: bool
    reason: str


def apply_transition(
    delivery: NotificationDelivery,
    new_status: str,
    *,
    now: datetime,
    error_message: str | None = None,
    failure_category: str | None = None,
    provider_message_id: str | None = None,
) -> TransitionResult:
    """Attempt to move `delivery` to `new_status`, mutating it in place only
    if the transition is valid. Caller is responsible for flush/commit.

    Rules:
    - Same status reported again -> no-op ("duplicate"), timestamps untouched.
    - Current status already terminal -> no-op ("already_terminal"); this is
      what makes duplicate/out-of-order callbacks against an already-READ or
      already-FAILED row inert.
    - `new_status` is a terminal failure/skip/cancel/expire outcome -> always
      allowed from any non-terminal current status (a send can fail at any
      stage of its progress).
    - `new_status` is a progress-path status -> allowed only if its rank is
      strictly greater than the current rank; anything else is regression or
      out-of-order and is rejected ("regression_or_out_of_order").
    - The timestamp field for `new_status` (see _TIMESTAMP_FIELD_FOR_STATUS)
      is set only when the transition is actually applied, and only if not
      already set — a duplicate never overwrites an existing timestamp.
    """
    current = delivery.status

    if current == new_status:
        return TransitionResult(applied=False, reason="duplicate")

    if is_terminal(current):
        return TransitionResult(applied=False, reason="already_terminal")

    if new_status not in _TERMINAL_FAILURE_STATUSES:
        new_rank = rank(new_status)
        cur_rank = rank(current)
        if new_rank is None:
            return TransitionResult(applied=False, reason="unknown_status")
        if cur_rank is None or new_rank <= cur_rank:
            return TransitionResult(applied=False, reason="regression_or_out_of_order")

    delivery.status = new_status
    field = _TIMESTAMP_FIELD_FOR_STATUS.get(new_status)
    if field is not None and getattr(delivery, field, None) is None:
        setattr(delivery, field, now)
    if error_message is not None:
        delivery.error_message = error_message
    if failure_category is not None:
        delivery.failure_category = failure_category
    if provider_message_id is not None:
        delivery.provider_message_id = provider_message_id
    return TransitionResult(applied=True, reason="applied")


__all__ = ["TransitionResult", "apply_transition", "is_terminal", "rank"]

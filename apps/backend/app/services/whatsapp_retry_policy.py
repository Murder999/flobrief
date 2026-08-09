"""Typed retry classification + backoff policy for WhatsApp deliveries
(Part 6B-3).

Scope: this module only classifies *our own outbound send attempt* failures
(the HTTP call this backend makes to Twilio's Messages API) — never a
provider status *callback* reporting delivery failure for a message Twilio
already accepted (that path has no retry: a new send would be a new,
separate message, not a retry of the old one; see whatsapp_provider.py /
webhooks.py). A failure category is only ever retryable if it means "we
don't know whether Twilio received this send" or "Twilio's side is
temporarily unavailable" — never "Twilio understood and rejected it".
"""

from __future__ import annotations

import random

# Transient — safe to retry with backoff. All of these mean either "we don't
# know what happened" (timeout/connection/network) or "the other side told us
# to slow down / try again" (rate_limited, server_error).
RETRYABLE_CATEGORIES: frozenset[str] = frozenset(
    {
        "timeout",
        "connection_error",
        "network_error",
        "server_error",
        "rate_limited",
    }
)

# Permanent — Twilio understood the request and rejected it for a reason a
# retry cannot fix. Includes every non-retryable category referenced by the
# Part 6B-3 spec even where nothing in this codebase raises it yet, so the
# classification surface is stable for callers.
NON_RETRYABLE_CATEGORIES: frozenset[str] = frozenset(
    {
        "invalid_recipient",
        "no_consent",
        "opt_out",
        "invalid_e164",
        "template_missing",
        "template_rejected",
        "template_disabled",
        "invalid_content_sid",
        "sender_not_whatsapp_enabled",
        "invalid_variables",
        "permission",
        "demo_tenant",
        "auth",
        "provider_reported_failure",
        "unknown",
    }
)

# A category this module has never heard of is treated as non-retryable —
# retrying blind on an unclassified failure risks exactly the "sonsuz retry"
# (infinite retry) outcome the spec explicitly forbids.
DEFAULT_UNKNOWN_CATEGORY = "unknown"

MAX_ATTEMPTS = 5
BASE_DELAY_SECONDS = 30.0
MAX_DELAY_SECONDS = 3600.0
JITTER_RATIO = 0.2


def is_retryable(category: str | None) -> bool:
    if category is None:
        return False
    return category in RETRYABLE_CATEGORIES


def is_attempt_budget_exhausted(attempt_count: int) -> bool:
    return attempt_count >= MAX_ATTEMPTS


def compute_backoff_seconds(attempt_count: int, *, rng: random.Random | None = None) -> float:
    """`attempt_count` is the number of attempts already made (>= 1) — the
    delay computed here is for the *next* one. Exponential backoff doubling
    per attempt, capped at MAX_DELAY_SECONDS, with up to +/-JITTER_RATIO
    jitter so many simultaneously-failing deliveries don't all wake up and
    hit the provider in the same instant."""
    source = rng or random
    attempt_count = max(attempt_count, 1)
    raw = min(BASE_DELAY_SECONDS * (2 ** (attempt_count - 1)), MAX_DELAY_SECONDS)
    jitter = raw * JITTER_RATIO
    delay = raw + source.uniform(-jitter, jitter)
    return max(1.0, delay)


__all__ = [
    "DEFAULT_UNKNOWN_CATEGORY",
    "MAX_ATTEMPTS",
    "NON_RETRYABLE_CATEGORIES",
    "RETRYABLE_CATEGORIES",
    "compute_backoff_seconds",
    "is_attempt_budget_exhausted",
    "is_retryable",
]

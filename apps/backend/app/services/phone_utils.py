"""Shared phone-number normalization to E.164.

Single source of truth for the WhatsApp test-send flow. Existing call sites in
schemas/auth.py and schemas/whatsapp_provider.py have their own inline
validators predating this helper and are left untouched (see docs/DECISIONS.md
DECISION-049) — consolidating them is a follow-up, not done here.
"""

from __future__ import annotations

import re

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")
_TR_DIAL_CODE = "+90"


def normalize_e164(raw: str) -> str | None:
    """Normalize a user-entered phone number to E.164, or return None if invalid.

    Handles: surrounding whitespace, spaces/dashes/parens inside the number,
    a Turkish national leading "0" (converted to +90), and a bare "+"-prefixed
    international number. Never raises.
    """
    if not raw:
        return None

    cleaned = re.sub(r"[\s\-()]", "", raw.strip())
    if not cleaned:
        return None

    if cleaned.startswith("whatsapp:"):
        cleaned = cleaned[len("whatsapp:") :]

    if cleaned.startswith("+"):
        candidate = cleaned
    elif cleaned.startswith("00"):
        candidate = "+" + cleaned[2:]
    elif cleaned.startswith("0"):
        # Turkish national format: 0XXX XXX XX XX → +90XXXXXXXXXX
        candidate = _TR_DIAL_CODE + cleaned[1:]
    else:
        candidate = "+" + cleaned

    if not _E164_RE.match(candidate):
        return None
    return candidate


def mask_phone_e164(phone: str) -> str:
    """Mask a phone number for display — keep the leading dial-code-ish
    prefix and last two digits, hide the rest. Never used to derive a
    reversible value; safe to store and return in API responses."""
    clean = phone.replace("whatsapp:", "")
    if len(clean) <= 6:
        return "***"
    return clean[:4] + "***" + clean[-2:]

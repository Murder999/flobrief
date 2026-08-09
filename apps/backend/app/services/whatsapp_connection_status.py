"""Computes the WhatsApp provider connection status shown in the UI.

Real states only — never fabricated. `connected`/`degraded`/`error` are only
ever reachable if a `test_connection()` call has actually run (via the
platform-admin /verify-connection endpoint) and its result was persisted on
`PlatformProviderSetting.last_connection_status`. This module itself makes no
network calls — it's a pure read of stored DB fields, safe to call on every
page load.
"""

from __future__ import annotations

from typing import Literal

from app.core.config import settings
from app.models.platform_provider_settings import PlatformProviderSetting

ConnectionStatus = Literal[
    "disabled", "not_configured", "sandbox", "connected", "degraded", "error"
]

_REQUIRED_FIELDS = ("encrypted_account_sid", "encrypted_auth_token", "encrypted_whatsapp_from")


def compute_connection_status(row: PlatformProviderSetting | None) -> ConnectionStatus:
    if not settings.WHATSAPP_NOTIFICATIONS_ENABLED:
        return "disabled"

    if row is None or not row.is_enabled:
        return "not_configured"

    if any(not getattr(row, field) for field in _REQUIRED_FIELDS):
        return "not_configured"

    if row.last_connection_status == "ok":
        return "connected"
    if row.last_connection_status == "degraded":
        return "degraded"
    if row.last_connection_status == "error":
        return "error"

    # Fully configured but never actually verified against Twilio yet.
    return "sandbox"

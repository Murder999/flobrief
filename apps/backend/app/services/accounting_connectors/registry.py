"""Connector registry (plan §10): the single chokepoint that resolves a
`provider` string to a concrete `AccountingConnectorInterface` instance.

SSRF-prevention boundary (plan §10/§12): v1 makes zero outbound HTTP calls,
so there is no SSRF surface today. But this function is *where* that surface
would open up in the future, so the rule is recorded here, at the point of
maximum leverage: any future real connector (quickbooks/xero/logo/parasut/
mikro) MUST hardcode its provider base URL as a server-side constant inside
its own connector module. It must NEVER read a host/URL out of
`AccountingConnector.config` (agency-editable JSONB) or any other
user-supplied input and use it to construct an outbound request — doing so
would let a tenant point "QuickBooks sync" at an arbitrary internal address.
`config` may only ever hold non-secret, non-networking settings (e.g. a
provider-side company/tenant id chosen from a validated list).
"""

from __future__ import annotations

from app.models.enums import AccountingProvider
from app.services.accounting_connectors.base import AccountingConnectorInterface
from app.services.accounting_connectors.manual_connector import ManualConnector


def get_connector(provider: str) -> AccountingConnectorInterface:
    """Resolve a `provider` string to its connector implementation.

    Only `manual` is ever actually usable. Every other `AccountingProvider`
    enum value is accepted for validation/UI purposes elsewhere in the
    system, but reaching this function with one of them raises
    `NotImplementedError` — no HTTP client code exists for them at all.
    """
    if provider == AccountingProvider.MANUAL.value:
        return ManualConnector()
    raise NotImplementedError(f"{provider} connector not yet implemented")

"""Connector interface (plan §10): the single contract every accounting
provider — real or manual — must satisfy. `AccountingConnectorService`
dispatches through this `Protocol` only; it never imports a concrete
provider class directly (see `registry.py`).

None of these methods perform I/O themselves at the interface level — each
concrete implementation owns its own transport. `ManualConnector`
(`manual_connector.py`) is the only implementation shipped in this phase and
makes zero network calls.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AccountingConnectorInterface(Protocol):
    """Provider-agnostic accounting/invoicing operations.

    `brand`/`invoice`/`payment` parameters are duck-typed domain objects
    (`app.models.brand.Brand`, `app.models.client_invoice.ClientInvoice`,
    `app.models.accounting_connector.Payment`) — the Protocol intentionally
    avoids importing those modules to keep this interface free of any
    provider-specific coupling.
    """

    async def test_connection(self) -> bool:
        """Verify the configured credentials/connectivity. Never raises for
        an expected "not reachable" outcome — returns False instead."""
        ...

    async def create_or_update_contact(self, brand: Any) -> str:
        """Create/update the brand as a contact on the provider side.
        Returns the provider's contact id."""
        ...

    async def create_invoice(self, invoice: Any, lines: list[Any]) -> str:
        """Create the invoice on the provider side. Returns the provider's
        external invoice id."""
        ...

    async def get_invoice_status(self, external_id: str) -> str:
        """Return the provider's status string for a previously created
        invoice."""
        ...

    async def cancel_invoice(self, external_id: str) -> None:
        """Cancel/void the invoice on the provider side."""
        ...

    async def record_payment(self, external_invoice_id: str, payment: Any) -> str:
        """Record a payment against the provider's invoice. Returns the
        provider's payment id."""
        ...

    async def fetch_payments(self, since: Any) -> list[dict]:
        """Return provider-reported payments since a given point in time."""
        ...

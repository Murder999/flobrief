"""ManualConnector: the only real implementation of
`AccountingConnectorInterface` in this phase (plan §10). Makes ZERO network
calls anywhere — every method is pure/local. `create_invoice` returns the
`ClientInvoice.id` itself as the "external id" (there is no external system);
`fetch_payments` always returns an empty list (there is no provider feed to
poll)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.client_invoice import ClientInvoice


class ManualConnector:
    """No-op / local-only connector for agencies that track accounting
    manually (outside Flobrief) or simply haven't connected a real provider
    yet. Every method is synchronous in spirit (no I/O) but declared async to
    satisfy `AccountingConnectorInterface`."""

    async def test_connection(self) -> bool:
        return True

    async def create_or_update_contact(self, brand: Any) -> str:
        return str(brand.id)

    async def create_invoice(self, invoice: ClientInvoice, lines: list[Any]) -> str:
        return str(invoice.id)

    async def get_invoice_status(self, external_id: str) -> str:
        return "unknown"

    async def cancel_invoice(self, external_id: str) -> None:
        return None

    async def record_payment(self, external_invoice_id: str, payment: Any) -> str:
        return str(payment.id)

    async def fetch_payments(self, since: datetime) -> list[dict]:
        return []

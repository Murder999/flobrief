"""AccountingConnectorService (plan §3/§7/§10): connector CRUD with
credential encryption, and idempotent dispatch through the connector
registry.

Idempotency (plan §3/§10): every dispatch is keyed by
`f"{connector_id}:{operation}:{related_invoice_id or 'na'}"`. A retry with
the same key is a no-op read of the prior `ConnectorSyncLog` row — the
underlying connector method is never invoked a second time for the same
key, regardless of whether the first attempt succeeded or failed (a failed
attempt must be explicitly retried via a *new* trigger — e.g. a new
`sync-invoice` call after the invoice state changes — not silently retried
under the same key).

Credential handling (plan §3/§12): raw credentials are encrypted with
`SecretEncryptionService.encrypt()` before being stored in
`encrypted_credentials`. That column, and any decrypted value, is never
placed on `AccountingConnectorRead` (see `app/schemas/accounting_connector.py`)
or written into a `ConnectorSyncLog` payload — `_redact` strips any
credential-shaped key from `request_payload`/`response_payload` as
defense-in-depth even though `ManualConnector` never handles real secrets.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.rbac import Permission, get_permissions_for_agency_role
from app.models.accounting_connector import AccountingConnector, ConnectorSyncLog
from app.models.enums import (
    AgencyMemberStatus,
    ConnectorStatus,
    ConnectorSyncStatus,
    NotificationEventType,
)
from app.repositories.accounting_connector import AccountingConnectorRepository
from app.repositories.agency_member import AgencyMemberRepository
from app.repositories.client_invoice import ClientInvoiceRepository
from app.repositories.connector_sync_log import ConnectorSyncLogRepository
from app.schemas.accounting_connector import AccountingConnectorCreate, AccountingConnectorUpdate
from app.services.accounting_connectors.registry import get_connector
from app.services.notification_dispatcher import NotificationDispatcher
from app.services.secret_encryption import SecretEncryptionService

_CREDENTIAL_KEY_MARKERS = (
    "key",
    "secret",
    "token",
    "password",
    "credential",
    "auth",
    "apikey",
)


def _redact(payload: dict | None) -> dict | None:
    if payload is None:
        return None
    redacted: dict[str, Any] = {}
    for k, v in payload.items():
        if isinstance(v, dict):
            redacted[k] = _redact(v)
        elif any(marker in k.lower() for marker in _CREDENTIAL_KEY_MARKERS):
            redacted[k] = "[REDACTED]"
        else:
            redacted[k] = v
    return redacted


class AccountingConnectorService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AccountingConnectorRepository(db)
        self._sync_log_repo = ConnectorSyncLogRepository(db)
        self._invoice_repo = ClientInvoiceRepository(db)
        self._member_repo = AgencyMemberRepository(db)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create(
        self, agency_id: uuid.UUID, actor_id: uuid.UUID, data: AccountingConnectorCreate
    ) -> AccountingConnector:
        existing = await self._repo.get_by_provider(agency_id, data.provider)
        if existing is not None:
            raise ConflictError(
                f"Bu ajans için '{data.provider}' sağlayıcısına ait bir bağlayıcı zaten var"
            )
        encrypted = self._encrypt_credentials(data.credentials)
        connector = await self._repo.create(
            {
                "agency_id": agency_id,
                "provider": data.provider,
                "status": ConnectorStatus.NOT_CONFIGURED.value,
                "encrypted_credentials": encrypted,
                "config": data.config,
                "created_by_id": actor_id,
            }
        )
        await self._db.commit()
        await self._db.refresh(connector)
        return connector

    async def list_for_agency(self, agency_id: uuid.UUID) -> list[AccountingConnector]:
        return await self._repo.list_for_agency(agency_id)

    async def get(self, agency_id: uuid.UUID, connector_id: uuid.UUID) -> AccountingConnector:
        return await self._get_or_404(agency_id, connector_id)

    async def update(
        self,
        agency_id: uuid.UUID,
        connector_id: uuid.UUID,
        data: AccountingConnectorUpdate,
    ) -> AccountingConnector:
        connector = await self._get_or_404(agency_id, connector_id)
        update_data: dict[str, Any] = {}
        if data.credentials is not None:
            update_data["encrypted_credentials"] = self._encrypt_credentials(data.credentials)
        if data.config is not None:
            update_data["config"] = data.config
        updated = await self._repo.update(connector, update_data)
        await self._db.commit()
        await self._db.refresh(updated)
        return updated

    async def delete(self, agency_id: uuid.UUID, connector_id: uuid.UUID) -> None:
        connector = await self._get_or_404(agency_id, connector_id)
        await self._repo.soft_delete(connector)
        await self._db.commit()

    def _encrypt_credentials(self, credentials: dict[str, str] | None) -> str | None:
        if not credentials:
            return None
        return SecretEncryptionService.encrypt(json.dumps(credentials, sort_keys=True))

    async def _get_or_404(
        self, agency_id: uuid.UUID, connector_id: uuid.UUID
    ) -> AccountingConnector:
        connector = await self._repo.get_by_id(connector_id, agency_id)
        if connector is None:
            raise NotFoundError("Muhasebe bağlayıcısı", str(connector_id))
        return connector

    # ------------------------------------------------------------------
    # Idempotent dispatch
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        connector: AccountingConnector,
        operation: str,
        agency_id: uuid.UUID,
        related_invoice_id: uuid.UUID | None,
        request_payload: dict,
        call: Any,
    ) -> tuple[Any, ConnectorSyncLog]:
        """Runs `call()` at most once per idempotency key. A prior row for
        the same key — success or failure — is returned as-is without
        invoking `call` again."""
        idempotency_key = f"{connector.id}:{operation}:{related_invoice_id or 'na'}"
        existing = await self._sync_log_repo.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            # No-op replay: the underlying connector method is NEVER
            # invoked again for a key that already has a log row, whether
            # that prior attempt succeeded or failed. A failed prior
            # attempt re-raises the same error info instead of silently
            # returning a hollow success — the caller sees identical
            # behavior on first call and on replay.
            if existing.status == ConnectorSyncStatus.FAILED.value:
                raise ConflictError(
                    existing.error_message or "Önceki senkronizasyon denemesi başarısız oldu"
                )
            value = existing.response_payload.get("value") if existing.response_payload else None
            return value, existing

        try:
            result = await call()
        except Exception as exc:
            log = await self._sync_log_repo.create(
                {
                    "connector_id": connector.id,
                    "agency_id": agency_id,
                    "operation": operation,
                    "related_invoice_id": related_invoice_id,
                    "idempotency_key": idempotency_key,
                    "request_payload": _redact(request_payload),
                    "response_payload": None,
                    "status": ConnectorSyncStatus.FAILED.value,
                    "error_message": str(exc),
                }
            )
            await self._db.commit()
            raise
        else:
            response_payload = _redact({"value": result})
            log = await self._sync_log_repo.create(
                {
                    "connector_id": connector.id,
                    "agency_id": agency_id,
                    "operation": operation,
                    "related_invoice_id": related_invoice_id,
                    "idempotency_key": idempotency_key,
                    "request_payload": _redact(request_payload),
                    "response_payload": response_payload,
                    "status": ConnectorSyncStatus.SUCCESS.value,
                    "error_message": None,
                }
            )
            await self._db.commit()
            return result, log

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    async def test_connection(
        self, agency_id: uuid.UUID, connector_id: uuid.UUID
    ) -> tuple[bool, ConnectorSyncLog]:
        connector = await self._get_or_404(agency_id, connector_id)
        impl = get_connector(connector.provider)  # raises NotImplementedError cleanly

        async def _call() -> bool:
            return await impl.test_connection()

        result, log = await self._dispatch(
            connector, "test_connection", agency_id, None, {"provider": connector.provider}, _call
        )
        connected = bool(result)
        now = datetime.now(UTC)
        await self._repo.update(
            connector,
            {
                "status": ConnectorStatus.CONNECTED.value
                if connected
                else ConnectorStatus.ERROR.value,
                "last_tested_at": now,
                "last_error": None if connected else "Bağlantı testi başarısız oldu",
            },
        )
        await self._db.commit()
        return connected, log

    async def sync_invoice(
        self, agency_id: uuid.UUID, connector_id: uuid.UUID, invoice_id: uuid.UUID
    ) -> tuple[str, ConnectorSyncLog]:
        connector = await self._get_or_404(agency_id, connector_id)
        invoice = await self._invoice_repo.get_by_id(invoice_id, agency_id)
        if invoice is None:
            raise NotFoundError("Fatura", str(invoice_id))
        lines = await self._invoice_repo.list_lines(invoice.id)
        impl = get_connector(connector.provider)  # raises NotImplementedError cleanly

        async def _call() -> str:
            return await impl.create_invoice(invoice, lines)

        # Dedupe INVOICE_SEND_FAILED against the idempotency log itself: a
        # prior FAILED row for this exact operation means any exception
        # `_dispatch` raises below is a cached replay of an already-notified
        # failure, not a new one — only a *fresh* failure (no such row yet)
        # should emit a new notification.
        idempotency_key = f"{connector.id}:create_invoice:{invoice.id}"
        prior_log = await self._sync_log_repo.get_by_idempotency_key(idempotency_key)
        already_failed = (
            prior_log is not None and prior_log.status == ConnectorSyncStatus.FAILED.value
        )

        try:
            external_id, log = await self._dispatch(
                connector,
                "create_invoice",
                agency_id,
                invoice.id,
                {"invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number},
                _call,
            )
        except Exception:
            if not already_failed:
                await self._notify_send_failed(agency_id, invoice, connector)
            raise

        now = datetime.now(UTC)
        await self._repo.update(connector, {"last_sync_at": now})
        if log.status == ConnectorSyncStatus.SUCCESS.value:
            await self._invoice_repo.update(
                invoice,
                {
                    "accounting_provider": connector.provider,
                    "external_invoice_id": external_id,
                    "provider_status": "synced",
                    "provider_error": None,
                },
            )
        await self._db.commit()
        return external_id, log

    async def _notify_send_failed(
        self,
        agency_id: uuid.UUID,
        invoice: Any,
        connector: AccountingConnector,
    ) -> None:
        """Notifies whoever manages accounting integrations for this agency
        — never the brand — that a connector dispatch for this invoice
        failed. Deliberately does not carry the raw exception text into the
        notification payload — the full (already-redacted) error is on the
        `ConnectorSyncLog` row for anyone who needs the detail; the
        notification itself only needs to say "this needs attention"."""
        members = await self._member_repo.list_by_agency(agency_id)
        recipient_ids = [
            m.user_id
            for m in members
            if m.status == AgencyMemberStatus.ACTIVE.value
            and Permission.ACCOUNTING_INTEGRATION_MANAGE in get_permissions_for_agency_role(m.role)
        ]
        if not recipient_ids:
            return
        await NotificationDispatcher(self._db).emit(
            NotificationEventType.INVOICE_SEND_FAILED.value,
            payload={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "connector_id": str(connector.id),
                "provider": connector.provider,
                "summary": f"{invoice.invoice_number} numaralı faturanın muhasebe "
                "entegrasyonuna gönderimi başarısız oldu.",
            },
            agency_id=agency_id,
            brand_id=invoice.brand_id,
            actor_user_id=None,
            recipient_ids=recipient_ids,
        )
        await self._db.commit()

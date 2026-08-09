from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.enums import AccountingProvider

_VALID_PROVIDERS = {p.value for p in AccountingProvider}


class AccountingConnectorCreate(BaseModel):
    """Explicit field allowlist (plan §12 mass-assignment guard). `credentials`
    is a plain dict of raw secret key/value pairs supplied by the caller —
    the service encrypts it with `SecretEncryptionService` before it ever
    touches the DB and it is never echoed back in any response. `config`
    holds only non-secret settings and must never contain a host/URL used
    for outbound requests (plan §10 registry chokepoint)."""

    provider: str
    credentials: dict[str, str] | None = None
    config: dict | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in _VALID_PROVIDERS:
            raise ValueError(f"Geçersiz sağlayıcı: {v}")
        return v


class AccountingConnectorUpdate(BaseModel):
    credentials: dict[str, str] | None = None
    config: dict | None = None


class AccountingConnectorRead(BaseModel):
    """Deliberately excludes `encrypted_credentials` (and any decrypted
    credential value) — the field simply does not exist on this schema, so
    there is nothing to accidentally serialize (plan §3/§12)."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    provider: str
    status: str
    config: dict | None
    last_tested_at: datetime | None
    last_sync_at: datetime | None
    last_error: str | None
    created_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ConnectorSyncLogRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    connector_id: uuid.UUID
    operation: str
    related_invoice_id: uuid.UUID | None
    status: str
    error_message: str | None
    created_at: datetime


class ConnectorTestConnectionResult(BaseModel):
    connected: bool
    tested_at: datetime


class ConnectorSyncInvoiceResult(BaseModel):
    external_invoice_id: str
    status: str
    sync_log: ConnectorSyncLogRead

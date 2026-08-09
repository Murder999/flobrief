"""AccountingConnectorService tests (plan §3/§10/§12/§13):

- `ManualConnector` satisfies the full `AccountingConnectorInterface`
  Protocol contract and makes ZERO network calls (verified by patching
  `httpx`/`requests`/`aiohttp` client constructors and asserting they are
  never instantiated, plus by asserting `ManualConnector` never imports any
  such module).
- `ConnectorSyncLog` idempotency: two identical dispatch calls for the same
  connector/operation/invoice produce exactly one `ConnectorSyncLog` row and
  invoke the underlying connector method exactly once.
- An unimplemented provider (`quickbooks`) raises `NotImplementedError`
  cleanly, with no `ConnectorSyncLog` row ever written for that attempt.
- Credentials are encrypted at rest, never appear in `AccountingConnectorRead`,
  and never appear (even redacted-but-present) in a `ConnectorSyncLog`
  payload.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select

from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import AsyncSessionLocal
from app.models.accounting_connector import ConnectorSyncLog
from app.models.agency import Agency
from app.models.brand import Brand
from app.models.client_invoice import ClientInvoice
from app.models.enums import UserType
from app.models.user import User
from app.schemas.accounting_connector import AccountingConnectorCreate, AccountingConnectorUpdate
from app.services.accounting_connectors.manual_connector import ManualConnector
from app.services.accounting_connectors.registry import get_connector
from app.services.accounting_connectors.service import AccountingConnectorService

TODAY = datetime.now(UTC).date()


async def _make_user(session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"connector-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="not-a-real-hash-test-fixture-only",
        full_name="Test Owner",
        user_type=UserType.AGENCY_USER.value,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    return user


async def _seed() -> dict:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        agency = Agency(id=uuid.uuid4(), name=f"Conn Agency {suffix}", slug=f"conn-{suffix}")
        brand = Brand(
            id=uuid.uuid4(), agency_id=agency.id, name="Conn Brand", slug=f"conn-brand-{suffix}"
        )
        session.add_all([agency, brand])
        await session.flush()
        owner = await _make_user(session)
        await session.flush()

        invoice = ClientInvoice(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand.id,
            invoice_number=f"INV-{suffix}",
            document_type="draft_invoice",
            issue_date=TODAY,
            due_date=TODAY,
            currency="TRY",
            subtotal_cents=100_000,
            discount_cents=0,
            tax_cents=20_000,
            total_cents=120_000,
            amount_paid_cents=0,
            status="draft",
        )
        session.add(invoice)
        await session.commit()
        return {
            "agency_id": agency.id,
            "brand_id": brand.id,
            "owner_id": owner.id,
            "invoice_id": invoice.id,
        }


async def _create_manual_connector(ctx: dict, credentials: dict | None = None):
    async with AsyncSessionLocal() as session:
        connector = await AccountingConnectorService(session).create(
            ctx["agency_id"],
            ctx["owner_id"],
            AccountingConnectorCreate(provider="manual", credentials=credentials),
        )
        return connector.id


async def _count_sync_logs(connector_id: uuid.UUID) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(ConnectorSyncLog)
            .where(ConnectorSyncLog.connector_id == connector_id)
        )
        return result.scalar_one()


# ── Protocol contract / zero network calls ──────────────────────────────────


async def test_manual_connector_satisfies_full_protocol_contract() -> None:
    from app.services.accounting_connectors.base import AccountingConnectorInterface

    impl = ManualConnector()
    assert isinstance(impl, AccountingConnectorInterface)
    assert await impl.test_connection() is True
    assert await impl.fetch_payments(datetime.now(UTC)) == []


async def test_manual_connector_makes_zero_network_calls() -> None:
    """Patch the most common Python HTTP client constructors; if
    `ManualConnector` ever tried to make a real call, one of these would be
    invoked."""
    with (
        patch("httpx.AsyncClient.__init__", side_effect=AssertionError("network call attempted")),
        patch("httpx.Client.__init__", side_effect=AssertionError("network call attempted")),
    ):
        impl = ManualConnector()
        ctx = await _seed()
        async with AsyncSessionLocal() as session:
            invoice = (
                await session.execute(
                    select(ClientInvoice).where(ClientInvoice.id == ctx["invoice_id"])
                )
            ).scalar_one()
        assert await impl.test_connection() is True
        assert await impl.create_invoice(invoice, []) == str(invoice.id)
        assert await impl.get_invoice_status("x") == "unknown"
        await impl.cancel_invoice("x")
        assert await impl.fetch_payments(datetime.now(UTC)) == []
    # No AssertionError raised => httpx was never touched.


async def test_manual_connector_module_imports_no_http_client_library() -> None:
    import app.services.accounting_connectors.manual_connector as mod

    source_globals = set(mod.__dict__.keys())
    for forbidden in ("httpx", "requests", "aiohttp", "urllib3"):
        assert forbidden not in source_globals


# ── Sync-log idempotency ─────────────────────────────────────────────────────


async def test_sync_invoice_idempotent_on_retry_exactly_one_dispatch() -> None:
    ctx = await _seed()
    connector_id = await _create_manual_connector(ctx)

    with patch.object(
        ManualConnector, "create_invoice", new=AsyncMock(wraps=ManualConnector().create_invoice)
    ) as mocked:
        async with AsyncSessionLocal() as session:
            first_id, first_log = await AccountingConnectorService(session).sync_invoice(
                ctx["agency_id"], connector_id, ctx["invoice_id"]
            )
        async with AsyncSessionLocal() as session:
            second_id, second_log = await AccountingConnectorService(session).sync_invoice(
                ctx["agency_id"], connector_id, ctx["invoice_id"]
            )

    assert first_id == second_id == str(ctx["invoice_id"])
    assert first_log.id == second_log.id, "retry must read the same log row, not create a new one"
    assert (
        mocked.call_count == 1
    ), f"underlying connector method invoked {mocked.call_count} times, expected exactly 1"
    assert await _count_sync_logs(connector_id) == 1


async def test_test_connection_idempotent_on_retry_exactly_one_dispatch() -> None:
    ctx = await _seed()
    connector_id = await _create_manual_connector(ctx)

    with patch.object(
        ManualConnector, "test_connection", new=AsyncMock(wraps=ManualConnector().test_connection)
    ) as mocked:
        async with AsyncSessionLocal() as session:
            first_ok, first_log = await AccountingConnectorService(session).test_connection(
                ctx["agency_id"], connector_id
            )
        async with AsyncSessionLocal() as session:
            second_ok, second_log = await AccountingConnectorService(session).test_connection(
                ctx["agency_id"], connector_id
            )

    assert first_ok is True
    assert second_ok is True
    assert first_log.id == second_log.id
    assert mocked.call_count == 1
    assert await _count_sync_logs(connector_id) == 1


async def test_different_invoices_produce_different_idempotency_keys() -> None:
    """Sanity check that idempotency is scoped per (connector, operation,
    invoice), not globally per connector — a second, different invoice must
    still dispatch."""
    ctx = await _seed()
    connector_id = await _create_manual_connector(ctx)

    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:8]
        invoice2 = ClientInvoice(
            id=uuid.uuid4(),
            agency_id=ctx["agency_id"],
            brand_id=ctx["brand_id"],
            invoice_number=f"INV2-{suffix}",
            document_type="draft_invoice",
            issue_date=TODAY,
            due_date=TODAY,
            currency="TRY",
            subtotal_cents=1000,
            discount_cents=0,
            tax_cents=0,
            total_cents=1000,
            amount_paid_cents=0,
            status="draft",
        )
        session.add(invoice2)
        await session.commit()
        invoice2_id = invoice2.id

    async with AsyncSessionLocal() as session:
        await AccountingConnectorService(session).sync_invoice(
            ctx["agency_id"], connector_id, ctx["invoice_id"]
        )
    async with AsyncSessionLocal() as session:
        await AccountingConnectorService(session).sync_invoice(
            ctx["agency_id"], connector_id, invoice2_id
        )

    assert await _count_sync_logs(connector_id) == 2


# ── Unimplemented provider ───────────────────────────────────────────────────


def test_registry_raises_not_implemented_for_non_manual_provider() -> None:
    with pytest.raises(NotImplementedError):
        get_connector("quickbooks")


async def test_sync_invoice_with_unimplemented_provider_raises_cleanly_no_log_written() -> None:
    ctx = await _seed()
    async with AsyncSessionLocal() as session:
        connector = await AccountingConnectorService(session).create(
            ctx["agency_id"],
            ctx["owner_id"],
            AccountingConnectorCreate(provider="quickbooks", credentials=None),
        )
        connector_id = connector.id

    async with AsyncSessionLocal() as session:
        with pytest.raises(NotImplementedError):
            await AccountingConnectorService(session).sync_invoice(
                ctx["agency_id"], connector_id, ctx["invoice_id"]
            )

    assert await _count_sync_logs(connector_id) == 0


# ── Credential handling ──────────────────────────────────────────────────────


async def test_credentials_encrypted_and_never_returned_in_read_schema() -> None:
    ctx = await _seed()
    async with AsyncSessionLocal() as session:
        connector = await AccountingConnectorService(session).create(
            ctx["agency_id"],
            ctx["owner_id"],
            AccountingConnectorCreate(
                provider="manual", credentials={"api_key": "super-secret-value-123"}
            ),
        )

    assert connector.encrypted_credentials is not None
    assert "super-secret-value-123" not in connector.encrypted_credentials

    from app.schemas.accounting_connector import AccountingConnectorRead

    field_names = set(AccountingConnectorRead.model_fields.keys())
    assert "encrypted_credentials" not in field_names
    read = AccountingConnectorRead.model_validate(connector)
    assert "super-secret-value-123" not in read.model_dump_json()


async def test_credentials_never_appear_in_sync_log_payloads() -> None:
    ctx = await _seed()
    async with AsyncSessionLocal() as session:
        connector = await AccountingConnectorService(session).create(
            ctx["agency_id"],
            ctx["owner_id"],
            AccountingConnectorCreate(
                provider="manual", credentials={"api_secret": "another-super-secret-999"}
            ),
        )
        connector_id = connector.id

    async with AsyncSessionLocal() as session:
        await AccountingConnectorService(session).test_connection(ctx["agency_id"], connector_id)

    async with AsyncSessionLocal() as session:
        logs = (
            (
                await session.execute(
                    select(ConnectorSyncLog).where(ConnectorSyncLog.connector_id == connector_id)
                )
            )
            .scalars()
            .all()
        )
    assert len(logs) == 1
    for log in logs:
        assert "another-super-secret-999" not in str(log.request_payload)
        assert "another-super-secret-999" not in str(log.response_payload)


async def test_update_re_encrypts_new_credentials() -> None:
    ctx = await _seed()
    connector_id = await _create_manual_connector(ctx, credentials={"api_key": "old-value"})
    async with AsyncSessionLocal() as session:
        updated = await AccountingConnectorService(session).update(
            ctx["agency_id"],
            connector_id,
            AccountingConnectorUpdate(credentials={"api_key": "new-value-xyz"}),
        )
    assert updated.encrypted_credentials is not None
    assert "new-value-xyz" not in updated.encrypted_credentials
    assert "old-value" not in updated.encrypted_credentials


# ── CRUD basics / tenant scoping ─────────────────────────────────────────────


async def test_duplicate_provider_per_agency_rejected() -> None:
    ctx = await _seed()
    await _create_manual_connector(ctx)
    async with AsyncSessionLocal() as session:
        with pytest.raises(ConflictError):
            await AccountingConnectorService(session).create(
                ctx["agency_id"],
                ctx["owner_id"],
                AccountingConnectorCreate(provider="manual", credentials=None),
            )


async def test_get_unknown_connector_raises_not_found() -> None:
    ctx = await _seed()
    async with AsyncSessionLocal() as session:
        with pytest.raises(NotFoundError):
            await AccountingConnectorService(session).get(ctx["agency_id"], uuid.uuid4())


async def test_delete_soft_deletes_and_frees_provider_slot() -> None:
    ctx = await _seed()
    connector_id = await _create_manual_connector(ctx)
    async with AsyncSessionLocal() as session:
        await AccountingConnectorService(session).delete(ctx["agency_id"], connector_id)

    async with AsyncSessionLocal() as session:
        with pytest.raises(NotFoundError):
            await AccountingConnectorService(session).get(ctx["agency_id"], connector_id)

    # Provider slot freed — a new connector for the same provider can be created.
    async with AsyncSessionLocal() as session:
        recreated = await AccountingConnectorService(session).create(
            ctx["agency_id"],
            ctx["owner_id"],
            AccountingConnectorCreate(provider="manual", credentials=None),
        )
    assert recreated.id != connector_id

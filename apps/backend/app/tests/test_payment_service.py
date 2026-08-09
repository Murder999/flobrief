"""PaymentService tests (plan §3/§7/§13): partial/full/overpayment-rejected/
overpayment-allowed-when-flagged, duplicate `external_payment_id` rejected,
payment against a `cancelled` invoice rejected, and `ClientInvoice.status`
transitions correctly (draft -> partially_paid -> paid) as payments accrue."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.exceptions import ConflictError, ValidationError
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.brand import Brand
from app.models.client_invoice import ClientInvoice
from app.models.enums import UserType
from app.models.user import User
from app.schemas.payment import PaymentCreate
from app.services.payment_service import PaymentService

TODAY = datetime.now(UTC).date()


async def _make_user(session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"payment-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="not-a-real-hash-test-fixture-only",
        full_name="Test Payer",
        user_type=UserType.AGENCY_USER.value,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    return user


async def _seed(*, total_cents: int = 100_000, status: str = "sent") -> dict:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        agency = Agency(id=uuid.uuid4(), name=f"Pay Agency {suffix}", slug=f"pay-{suffix}")
        brand = Brand(
            id=uuid.uuid4(), agency_id=agency.id, name="Pay Brand", slug=f"pay-brand-{suffix}"
        )
        session.add_all([agency, brand])
        await session.flush()
        actor = await _make_user(session)
        await session.flush()

        invoice = ClientInvoice(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand.id,
            invoice_number=f"PINV-{suffix}",
            document_type="draft_invoice",
            issue_date=TODAY,
            due_date=TODAY,
            currency="TRY",
            subtotal_cents=total_cents,
            discount_cents=0,
            tax_cents=0,
            total_cents=total_cents,
            amount_paid_cents=0,
            status=status,
        )
        session.add(invoice)
        await session.commit()
        return {
            "agency_id": agency.id,
            "brand_id": brand.id,
            "actor_id": actor.id,
            "invoice_id": invoice.id,
        }


async def _reload_invoice(invoice_id: uuid.UUID) -> ClientInvoice:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ClientInvoice).where(ClientInvoice.id == invoice_id))
        return result.scalar_one()


def _payment_payload(ctx: dict, amount_cents: int, **overrides) -> PaymentCreate:
    base = dict(
        brand_id=ctx["brand_id"],
        invoice_id=ctx["invoice_id"],
        amount_cents=amount_cents,
        currency="TRY",
        payment_method="bank_transfer",
        paid_at=datetime.now(UTC),
    )
    base.update(overrides)
    return PaymentCreate(**base)


# ── Partial / full payment & status transitions ─────────────────────────────


async def test_partial_payment_sets_status_partially_paid() -> None:
    ctx = await _seed(total_cents=100_000)
    async with AsyncSessionLocal() as session:
        payment = await PaymentService(session).record_payment(
            ctx["agency_id"], ctx["actor_id"], _payment_payload(ctx, 40_000)
        )
    assert payment.amount_cents == 40_000

    invoice = await _reload_invoice(ctx["invoice_id"])
    assert invoice.amount_paid_cents == 40_000
    assert invoice.status == "partially_paid"


async def test_full_payment_sets_status_paid_and_paid_at() -> None:
    ctx = await _seed(total_cents=100_000)
    async with AsyncSessionLocal() as session:
        await PaymentService(session).record_payment(
            ctx["agency_id"], ctx["actor_id"], _payment_payload(ctx, 100_000)
        )
    invoice = await _reload_invoice(ctx["invoice_id"])
    assert invoice.amount_paid_cents == 100_000
    assert invoice.status == "paid"
    assert invoice.paid_at is not None


async def test_two_partial_payments_accumulate_to_paid() -> None:
    ctx = await _seed(total_cents=100_000)
    async with AsyncSessionLocal() as session:
        await PaymentService(session).record_payment(
            ctx["agency_id"], ctx["actor_id"], _payment_payload(ctx, 60_000)
        )
    mid_invoice = await _reload_invoice(ctx["invoice_id"])
    assert mid_invoice.status == "partially_paid"

    async with AsyncSessionLocal() as session:
        await PaymentService(session).record_payment(
            ctx["agency_id"], ctx["actor_id"], _payment_payload(ctx, 40_000)
        )
    final_invoice = await _reload_invoice(ctx["invoice_id"])
    assert final_invoice.amount_paid_cents == 100_000
    assert final_invoice.status == "paid"


# ── Overpayment ───────────────────────────────────────────────────────────────


async def test_overpayment_rejected_by_default() -> None:
    ctx = await _seed(total_cents=100_000)
    async with AsyncSessionLocal() as session:
        with pytest.raises(ValidationError):
            await PaymentService(session).record_payment(
                ctx["agency_id"], ctx["actor_id"], _payment_payload(ctx, 150_000)
            )
    invoice = await _reload_invoice(ctx["invoice_id"])
    assert invoice.amount_paid_cents == 0
    assert invoice.status == "sent"


async def test_overpayment_allowed_when_explicitly_flagged() -> None:
    ctx = await _seed(total_cents=100_000)
    async with AsyncSessionLocal() as session:
        payment = await PaymentService(session).record_payment(
            ctx["agency_id"],
            ctx["actor_id"],
            _payment_payload(ctx, 150_000, allow_overpayment=True),
        )
    assert payment.amount_cents == 150_000
    invoice = await _reload_invoice(ctx["invoice_id"])
    assert invoice.amount_paid_cents == 150_000
    assert invoice.status == "paid"  # amount_paid_cents >= total_cents


# ── Duplicate external_payment_id ───────────────────────────────────────────


async def test_duplicate_external_payment_id_rejected() -> None:
    # external_payment_id is unique across the whole `payments` table (a
    # global partial unique index, not scoped per agency/invoice — see
    # Payment.__table_args__), so a hardcoded literal here would collide
    # with a leftover row from a previous run of this same test (conftest
    # has no per-test DB rollback) and make the *first*, "should succeed"
    # record_payment() call below raise unexpectedly on a re-run. A fresh
    # uuid suffix per run keeps this test repeatable without a DB reset.
    external_payment_id = f"ext-dup-{uuid.uuid4().hex[:12]}"
    ctx = await _seed(total_cents=100_000)
    async with AsyncSessionLocal() as session:
        await PaymentService(session).record_payment(
            ctx["agency_id"],
            ctx["actor_id"],
            _payment_payload(ctx, 10_000, external_payment_id=external_payment_id),
        )
    async with AsyncSessionLocal() as session:
        with pytest.raises(ConflictError):
            await PaymentService(session).record_payment(
                ctx["agency_id"],
                ctx["actor_id"],
                _payment_payload(ctx, 5_000, external_payment_id=external_payment_id),
            )


async def test_null_external_payment_id_does_not_collide() -> None:
    """Two payments with no external_payment_id must never be treated as
    duplicates of each other."""
    ctx = await _seed(total_cents=100_000)
    async with AsyncSessionLocal() as session:
        await PaymentService(session).record_payment(
            ctx["agency_id"], ctx["actor_id"], _payment_payload(ctx, 10_000)
        )
    async with AsyncSessionLocal() as session:
        second = await PaymentService(session).record_payment(
            ctx["agency_id"], ctx["actor_id"], _payment_payload(ctx, 10_000)
        )
    assert second.external_payment_id is None


# ── Cancelled invoice ─────────────────────────────────────────────────────────


async def test_payment_against_cancelled_invoice_rejected() -> None:
    ctx = await _seed(total_cents=100_000, status="cancelled")
    async with AsyncSessionLocal() as session:
        with pytest.raises(ConflictError):
            await PaymentService(session).record_payment(
                ctx["agency_id"], ctx["actor_id"], _payment_payload(ctx, 10_000)
            )


# ── Cross-brand invoice mismatch ─────────────────────────────────────────────


async def test_payment_rejects_invoice_belonging_to_different_brand() -> None:
    ctx = await _seed(total_cents=100_000)
    async with AsyncSessionLocal() as session:
        other_brand = Brand(
            id=uuid.uuid4(),
            agency_id=ctx["agency_id"],
            name="Other Brand",
            slug=f"other-brand-{uuid.uuid4().hex[:8]}",
        )
        session.add(other_brand)
        await session.commit()
        other_brand_id = other_brand.id

    async with AsyncSessionLocal() as session:
        with pytest.raises(ValidationError):
            await PaymentService(session).record_payment(
                ctx["agency_id"],
                ctx["actor_id"],
                _payment_payload(ctx, 10_000, brand_id=other_brand_id),
            )


# ── Unallocated/advance payment (no invoice_id) ─────────────────────────────


async def test_payment_without_invoice_is_recorded_as_unallocated() -> None:
    ctx = await _seed(total_cents=100_000)
    async with AsyncSessionLocal() as session:
        payment = await PaymentService(session).record_payment(
            ctx["agency_id"],
            ctx["actor_id"],
            _payment_payload(ctx, 10_000, invoice_id=None),
        )
    assert payment.invoice_id is None
    invoice = await _reload_invoice(ctx["invoice_id"])
    assert invoice.amount_paid_cents == 0  # untouched — payment wasn't allocated to it

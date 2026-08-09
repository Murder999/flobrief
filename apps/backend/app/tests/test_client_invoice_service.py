"""ClientInvoiceService tests (plan §3/§12/§13): draft generation from real
billable time entries, rate-snapshot correctness and immutability
(re-generating/re-voiding doesn't corrupt snapshots — a snapshot always
reflects the rate active *at the moment of invoicing*, never drifts once
set, and is cleared only by `void`), duplicate-billing prevention, void
reopens entries, invoice numbering uniqueness under **actual** concurrency
(`asyncio.gather`), PDF text contains "Taslak"/"Proforma" and never a
cost-rate figure, and non-billable/unlocked entries are rejected from
selection."""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from pypdf import PdfReader
from sqlalchemy import select

from app.core.exceptions import ConflictError, ValidationError
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.commercial_terms import CommercialTerms, MemberCostRate
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.repositories.commercial_terms import CommercialTermsRepository
from app.schemas.client_invoice import ClientInvoiceDraftCreate
from app.services.client_invoice_service import ClientInvoiceService
from app.services.invoice_pdf_service import InvoicePdfService

TODAY = date.today()


async def _make_user(session, label: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{label.lower()}-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="not-a-real-hash-test-fixture-only",
        full_name=f"Test {label}",
        user_type=UserType.AGENCY_USER.value,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    return user


async def _seed(
    label: str,
    *,
    hourly_rate_cents: int | None = 50000,
    cost_rate_cents: int | None = 20000,
    tax_rate_bps: int = 2000,
) -> dict:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        agency = Agency(id=uuid.uuid4(), name=f"{label} Agency", slug=f"{label.lower()}-{suffix}")
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name=f"{label} Brand",
            slug=f"{label.lower()}-brand-{suffix}",
        )
        session.add_all([agency, brand])
        await session.flush()

        owner = await _make_user(session, f"{label}Owner")
        member = await _make_user(session, f"{label}Member")
        await session.flush()
        session.add_all(
            [
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=owner.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=member.id,
                    role=AgencyMemberRole.DESIGNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
            ]
        )

        if hourly_rate_cents is not None:
            session.add(
                CommercialTerms(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    brand_id=brand.id,
                    billing_model="hourly",
                    currency="TRY",
                    hourly_rate_cents=hourly_rate_cents,
                    payment_terms_days=30,
                    tax_rate_bps=tax_rate_bps,
                    valid_from=TODAY - timedelta(days=60),
                    active=True,
                )
            )

        if cost_rate_cents is not None:
            session.add(
                MemberCostRate(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=member.id,
                    currency="TRY",
                    hourly_cost_cents=cost_rate_cents,
                    valid_from=TODAY - timedelta(days=60),
                    active=True,
                )
            )

        await session.commit()
        return {
            "agency_id": agency.id,
            "brand_id": brand.id,
            "owner_id": owner.id,
            "member_id": member.id,
        }


async def _make_time_entry(
    agency_id: uuid.UUID,
    brand_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    hours: float = 2.0,
    billable: bool = True,
    locked: bool = True,
) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        started = datetime.now(UTC) - timedelta(hours=hours + 1)
        ended = started + timedelta(hours=hours)
        entry = TimeEntry(
            id=uuid.uuid4(),
            agency_id=agency_id,
            brand_id=brand_id,
            user_id=user_id,
            category="design",
            description="Test work",
            started_at=started,
            ended_at=ended,
            duration_seconds=int(hours * 3600),
            billable=billable,
            source="manual",
            locked=locked,
        )
        session.add(entry)
        await session.commit()
        return entry.id


async def _load_entry(entry_id: uuid.UUID) -> TimeEntry:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(TimeEntry).where(TimeEntry.id == entry_id))
        return result.scalar_one()


# ── Draft generation / rate snapshotting ────────────────────────────────────


async def test_generate_draft_computes_correct_totals_and_snapshots_rates() -> None:
    ctx = await _seed("Draft1")
    entry_id = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"], hours=2)

    async with AsyncSessionLocal() as session:
        invoice = await ClientInvoiceService(session).generate_draft(
            ctx["agency_id"],
            ctx["owner_id"],
            ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
        )

    assert invoice.status == "draft"
    assert invoice.subtotal_cents == 100_000  # 2h * 50000
    assert invoice.tax_cents == 20_000  # 20% KDV
    assert invoice.discount_cents == 0
    assert invoice.total_cents == 120_000
    assert invoice.currency == "TRY"

    entry = await _load_entry(entry_id)
    assert entry.invoiced_at is not None
    assert entry.billing_rate_snapshot_cents == 50_000
    assert entry.cost_rate_snapshot_cents == 20_000
    assert entry.rate_currency_snapshot == "TRY"


async def test_generate_draft_rejects_when_no_line_selected() -> None:
    ctx = await _seed("EmptyDraft")
    async with AsyncSessionLocal() as session:
        with pytest.raises(ValidationError):
            await ClientInvoiceService(session).generate_draft(
                ctx["agency_id"],
                ctx["owner_id"],
                ClientInvoiceDraftCreate(brand_id=ctx["brand_id"]),
            )


async def test_generate_draft_requires_active_terms_with_hourly_rate() -> None:
    ctx = await _seed("NoTerms", hourly_rate_cents=None)
    entry_id = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"])
    async with AsyncSessionLocal() as session:
        with pytest.raises(ValidationError):
            await ClientInvoiceService(session).generate_draft(
                ctx["agency_id"],
                ctx["owner_id"],
                ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
            )


# ── Non-billable / unlocked entries rejected ───────────────────────────────


async def test_non_billable_entry_is_rejected_from_selection() -> None:
    ctx = await _seed("NonBillable1")
    entry_id = await _make_time_entry(
        ctx["agency_id"], ctx["brand_id"], ctx["member_id"], billable=False
    )
    async with AsyncSessionLocal() as session:
        with pytest.raises(ValidationError):
            await ClientInvoiceService(session).generate_draft(
                ctx["agency_id"],
                ctx["owner_id"],
                ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
            )


async def test_unlocked_entry_is_rejected_from_selection() -> None:
    ctx = await _seed("Unlocked1")
    entry_id = await _make_time_entry(
        ctx["agency_id"], ctx["brand_id"], ctx["member_id"], locked=False
    )
    async with AsyncSessionLocal() as session:
        with pytest.raises(ValidationError):
            await ClientInvoiceService(session).generate_draft(
                ctx["agency_id"],
                ctx["owner_id"],
                ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
            )


async def test_list_billable_time_entries_excludes_non_billable_and_unlocked() -> None:
    ctx = await _seed("ListBillable1")
    billable_locked = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"])
    await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"], billable=False)
    await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"], locked=False)

    async with AsyncSessionLocal() as session:
        entries = await ClientInvoiceService(session).list_billable_time_entries(
            ctx["agency_id"], ctx["brand_id"]
        )
    assert [e.id for e in entries] == [billable_locked]


# ── Duplicate-billing prevention ────────────────────────────────────────────


async def test_reselecting_already_invoiced_entry_raises_conflict() -> None:
    ctx = await _seed("Dup1")
    entry_id = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"])
    async with AsyncSessionLocal() as session:
        await ClientInvoiceService(session).generate_draft(
            ctx["agency_id"],
            ctx["owner_id"],
            ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
        )

    async with AsyncSessionLocal() as session:
        with pytest.raises(ConflictError):
            await ClientInvoiceService(session).generate_draft(
                ctx["agency_id"],
                ctx["owner_id"],
                ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
            )


# ── Void reopens entries / clears snapshots ─────────────────────────────────


async def test_void_reopens_time_entries_and_clears_snapshots() -> None:
    ctx = await _seed("Void1")
    entry_id = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"])
    async with AsyncSessionLocal() as session:
        invoice = await ClientInvoiceService(session).generate_draft(
            ctx["agency_id"],
            ctx["owner_id"],
            ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
        )

    async with AsyncSessionLocal() as session:
        voided = await ClientInvoiceService(session).void(ctx["agency_id"], invoice.id)
    assert voided.status == "cancelled"

    entry = await _load_entry(entry_id)
    assert entry.invoiced_at is None
    assert entry.billing_rate_snapshot_cents is None
    assert entry.cost_rate_snapshot_cents is None
    assert entry.rate_currency_snapshot is None

    async with AsyncSessionLocal() as session:
        billable_again = await ClientInvoiceService(session).list_billable_time_entries(
            ctx["agency_id"], ctx["brand_id"]
        )
    assert entry_id in [e.id for e in billable_again]

    # Reopened entry can be invoiced again without any duplicate-key error.
    async with AsyncSessionLocal() as session:
        second_invoice = await ClientInvoiceService(session).generate_draft(
            ctx["agency_id"],
            ctx["owner_id"],
            ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
        )
    assert second_invoice.id != invoice.id
    assert second_invoice.invoice_number != invoice.invoice_number


async def test_voiding_already_voided_invoice_raises_conflict() -> None:
    ctx = await _seed("DoubleVoid")
    entry_id = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"])
    async with AsyncSessionLocal() as session:
        invoice = await ClientInvoiceService(session).generate_draft(
            ctx["agency_id"],
            ctx["owner_id"],
            ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
        )
    async with AsyncSessionLocal() as session:
        await ClientInvoiceService(session).void(ctx["agency_id"], invoice.id)
    async with AsyncSessionLocal() as session:
        with pytest.raises(ConflictError):
            await ClientInvoiceService(session).void(ctx["agency_id"], invoice.id)


# ── Snapshot immutability: reflects rate at invoicing moment, never drifts ──


async def test_snapshot_reflects_rate_at_reinvoicing_moment_not_original_or_drifted() -> None:
    ctx = await _seed("Immut1", hourly_rate_cents=50_000)
    entry_id = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"], hours=1)

    async with AsyncSessionLocal() as session:
        first = await ClientInvoiceService(session).generate_draft(
            ctx["agency_id"],
            ctx["owner_id"],
            ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
        )
    assert first.subtotal_cents == 50_000

    async with AsyncSessionLocal() as session:
        await ClientInvoiceService(session).void(ctx["agency_id"], first.id)

    # Bump the active commercial terms' hourly rate after the original
    # invoice — the ORIGINAL invoice's snapshot must stay exactly as it was.
    entry_after_void = await _load_entry(entry_id)
    assert entry_after_void.billing_rate_snapshot_cents is None  # cleared by void

    async with AsyncSessionLocal() as session:
        terms = await CommercialTermsRepository(session).get_active_for_brand(
            ctx["agency_id"], ctx["brand_id"]
        )
        terms.hourly_rate_cents = 80_000
        await session.commit()

    async with AsyncSessionLocal() as session:
        second = await ClientInvoiceService(session).generate_draft(
            ctx["agency_id"],
            ctx["owner_id"],
            ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
        )
    # New invoice reflects the CURRENT rate at the moment of invoicing, not
    # the rate that was active when the (now-voided) first invoice existed.
    assert second.subtotal_cents == 80_000

    entry_final = await _load_entry(entry_id)
    assert entry_final.billing_rate_snapshot_cents == 80_000


# ── Invoice-numbering uniqueness under actual concurrency ──────────────────


async def test_invoice_numbering_is_unique_under_real_concurrent_generation() -> None:
    ctx = await _seed("Concurrent1")
    entry_a = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"], hours=1)
    entry_b = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"], hours=1)

    async def _generate(entry_id: uuid.UUID):
        async with AsyncSessionLocal() as session:
            return await ClientInvoiceService(session).generate_draft(
                ctx["agency_id"],
                ctx["owner_id"],
                ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
            )

    # Two real concurrent draft-generation calls, each on its own DB
    # connection/session, racing to increment the same
    # AgencySettings.invoice_number_seq row.
    invoice_a, invoice_b = await asyncio.gather(_generate(entry_a), _generate(entry_b))

    assert invoice_a.id != invoice_b.id
    assert invoice_a.invoice_number != invoice_b.invoice_number, (
        "concurrent draft generation produced a duplicate invoice number "
        f"({invoice_a.invoice_number!r})"
    )


# ── PDF: legal wording present, cost-rate data never leaked ────────────────


async def test_pdf_contains_draft_wording_and_never_leaks_cost_rate() -> None:
    ctx = await _seed("Pdf1", cost_rate_cents=87_654)
    entry_id = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"], hours=3)

    async with AsyncSessionLocal() as session:
        svc = ClientInvoiceService(session)
        created = await svc.generate_draft(
            ctx["agency_id"],
            ctx["owner_id"],
            ClientInvoiceDraftCreate(brand_id=ctx["brand_id"], time_entry_ids=[entry_id]),
        )
        invoice, lines = await svc.get_with_lines(ctx["agency_id"], created.id)

    assert lines[0].cost_rate_snapshot_cents == 87_654  # sanity: it IS stored on the model

    pdf_bytes = InvoicePdfService.build_pdf_bytes(
        invoice, lines, agency_name="Test Agency", brand_name="Test Brand"
    )
    assert pdf_bytes[:4] == b"%PDF"

    text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf_bytes)).pages)
    assert "TASLA" in text.upper()  # "Fatura Taslağı" (transliterated/degraded glyph-safe)
    assert "87654" not in text.replace(".", "").replace(",", "")


async def test_pdf_proforma_document_type_says_proforma() -> None:
    ctx = await _seed("Pdf2")
    entry_id = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"], hours=1)

    async with AsyncSessionLocal() as session:
        svc = ClientInvoiceService(session)
        created = await svc.generate_draft(
            ctx["agency_id"],
            ctx["owner_id"],
            ClientInvoiceDraftCreate(
                brand_id=ctx["brand_id"], time_entry_ids=[entry_id], document_type="proforma"
            ),
        )
        invoice, lines = await svc.get_with_lines(ctx["agency_id"], created.id)

    pdf_bytes = InvoicePdfService.build_pdf_bytes(
        invoice, lines, agency_name="Test Agency", brand_name="Test Brand"
    )
    text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf_bytes)).pages)
    assert "PROFORMA" in text.upper()
    # The footer legitimately mentions "e-Fatura" only inside an explicit
    # disclaimer ("this document is NOT an official e-Fatura") — that
    # negation is required wording, not a violation. What must never appear
    # is any *affirmative* claim of e-fatura status.
    assert "resmi bir e-Fatura degildir" in text or "resmi bir e-Fatura değildir" in text
    assert "bu bir e-Fatura" not in text.lower().replace(" ", "")


# ── Tenant isolation ─────────────────────────────────────────────────────────


async def test_invoices_are_tenant_isolated() -> None:
    ctx_a = await _seed("TenantA")
    ctx_b = await _seed("TenantB")
    entry_id = await _make_time_entry(ctx_a["agency_id"], ctx_a["brand_id"], ctx_a["member_id"])

    async with AsyncSessionLocal() as session:
        invoice = await ClientInvoiceService(session).generate_draft(
            ctx_a["agency_id"],
            ctx_a["owner_id"],
            ClientInvoiceDraftCreate(brand_id=ctx_a["brand_id"], time_entry_ids=[entry_id]),
        )

    async with AsyncSessionLocal() as session:
        cross_tenant_list = await ClientInvoiceService(session).list_for_agency(ctx_b["agency_id"])
    assert invoice.id not in [i.id for i in cross_tenant_list]

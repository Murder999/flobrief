"""ProfitabilityService tests (plan §7/§13): realized margin computed from
snapshotted (never live-recomputed) rates — including proof that bumping a
`MemberCostRate` AFTER invoicing does not retroactively change an
already-computed figure — missing-cost/missing-billing-rate flags that never
fabricate a zero-cost inflated margin, zero-revenue safety (no crash, margin
reported as `None`, never `0%`), and multi-currency non-summing at the
agency level (two brands with different currencies never collapse into one
blended total)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brief import Brief
from app.models.commercial_terms import CommercialTerms, MemberCostRate
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.repositories.member_cost_rate import MemberCostRateRepository
from app.schemas.client_invoice import ClientInvoiceDraftCreate
from app.services.client_invoice_service import ClientInvoiceService
from app.services.profitability_service import ProfitabilityService

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


async def _seed_agency_brand(
    label: str,
    *,
    currency: str = "TRY",
    hourly_rate_cents: int | None = 50_000,
    cost_rate_cents: int | None = 20_000,
    tax_rate_bps: int = 2000,
    agency_id: uuid.UUID | None = None,
) -> dict:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        if agency_id is None:
            agency = Agency(
                id=uuid.uuid4(), name=f"{label} Agency", slug=f"{label.lower()}-{suffix}"
            )
            session.add(agency)
            await session.flush()
            agency_id = agency.id

        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency_id,
            name=f"{label} Brand",
            slug=f"{label.lower()}-brand-{suffix}",
            currency=currency,
        )
        session.add(brand)
        await session.flush()

        owner = await _make_user(session, f"{label}Owner")
        member = await _make_user(session, f"{label}Member")
        await session.flush()
        session.add_all(
            [
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency_id,
                    user_id=owner.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency_id,
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
                    agency_id=agency_id,
                    brand_id=brand.id,
                    billing_model="hourly",
                    currency=currency,
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
                    agency_id=agency_id,
                    user_id=member.id,
                    currency=currency,
                    hourly_cost_cents=cost_rate_cents,
                    valid_from=TODAY - timedelta(days=60),
                    active=True,
                )
            )
        await session.commit()
        return {
            "agency_id": agency_id,
            "brand_id": brand.id,
            "owner_id": owner.id,
            "member_id": member.id,
        }


async def _make_brief(
    agency_id: uuid.UUID,
    brand_id: uuid.UUID,
    created_by_id: uuid.UUID,
    *,
    estimated_hours: float | None = None,
) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        brief = Brief(
            id=uuid.uuid4(),
            agency_id=agency_id,
            brand_id=brand_id,
            title="Test Brief",
            status="draft",
            created_by_id=created_by_id,
            estimated_hours=estimated_hours,
        )
        session.add(brief)
        await session.commit()
        return brief.id


async def _make_time_entry(
    agency_id: uuid.UUID,
    brand_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    brief_id: uuid.UUID | None = None,
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
            brief_id=brief_id,
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


async def _invoice_and_approve(agency_id, owner_id, brand_id, entry_id) -> None:
    """Generates a draft AND approves it — brand/agency-level revenue is
    computed from `ClientInvoice`/`ClientInvoiceLine` and deliberately
    excludes DRAFT status (an unapproved draft is not yet realized revenue),
    so tests exercising those scopes must advance past draft."""
    async with AsyncSessionLocal() as session:
        invoice = await ClientInvoiceService(session).generate_draft(
            agency_id,
            owner_id,
            ClientInvoiceDraftCreate(brand_id=brand_id, time_entry_ids=[entry_id]),
        )
    async with AsyncSessionLocal() as session:
        await ClientInvoiceService(session).approve(agency_id, invoice.id, owner_id)


# ── Realized margin from snapshots, immune to later rate changes ──────────


async def test_brief_realized_margin_matches_snapshot_and_survives_later_cost_rate_change() -> None:
    ctx = await _seed_agency_brand("Realized1", hourly_rate_cents=50_000, cost_rate_cents=20_000)
    brief_id = await _make_brief(ctx["agency_id"], ctx["brand_id"], ctx["owner_id"])
    entry_id = await _make_time_entry(
        ctx["agency_id"], ctx["brand_id"], ctx["member_id"], brief_id=brief_id, hours=2
    )
    await _invoice_and_approve(ctx["agency_id"], ctx["owner_id"], ctx["brand_id"], entry_id)

    async with AsyncSessionLocal() as session:
        result = await ProfitabilityService(session).get_brief_profitability(
            ctx["agency_id"], brief_id
        )

    assert len(result.realized) == 1
    r = result.realized[0]
    assert r.currency == "TRY"
    assert r.revenue_cents == 100_000  # 2h * 50000
    assert r.cost_cents == 40_000  # 2h * 20000
    assert r.gross_profit_cents == 60_000
    assert r.gross_margin_pct == 60.0
    assert r.margin_missing_reason is None

    # Bump the MemberCostRate AFTER invoicing — the already-invoiced entry's
    # frozen snapshot (and therefore this already-computed figure) must NOT
    # change, proving profitability reads snapshots, not live rates.
    async with AsyncSessionLocal() as session:
        repo = MemberCostRateRepository(session)
        rate = await repo.get_open_ended_for_user(ctx["agency_id"], ctx["member_id"])
        rate.hourly_cost_cents = 99_999
        await session.commit()

    async with AsyncSessionLocal() as session:
        result_after = await ProfitabilityService(session).get_brief_profitability(
            ctx["agency_id"], brief_id
        )
    r_after = result_after.realized[0]
    assert r_after.cost_cents == 40_000
    assert r_after.gross_profit_cents == 60_000
    assert r_after.gross_margin_pct == 60.0


# ── Missing cost rate: null, never a fabricated zero ───────────────────────


async def test_brief_missing_cost_rate_returns_null_cost_never_fabricated_zero() -> None:
    ctx = await _seed_agency_brand("MissingCost1", hourly_rate_cents=50_000, cost_rate_cents=None)
    brief_id = await _make_brief(ctx["agency_id"], ctx["brand_id"], ctx["owner_id"])
    entry_id = await _make_time_entry(
        ctx["agency_id"], ctx["brand_id"], ctx["member_id"], brief_id=brief_id, hours=2
    )
    await _invoice_and_approve(ctx["agency_id"], ctx["owner_id"], ctx["brand_id"], entry_id)

    async with AsyncSessionLocal() as session:
        result = await ProfitabilityService(session).get_brief_profitability(
            ctx["agency_id"], brief_id
        )

    r = result.realized[0]
    assert r.revenue_cents == 100_000  # revenue is real and known
    assert r.cost_cents is None  # NEVER 0 — 0 would fabricate a 100% margin
    assert r.gross_profit_cents is None
    assert r.gross_margin_pct is None
    assert r.margin_missing_reason == "cost_rate_eksik"


async def test_brand_missing_cost_rate_returns_null_cost_never_fabricated_zero() -> None:
    ctx = await _seed_agency_brand(
        "MissingCostBrand1", hourly_rate_cents=40_000, cost_rate_cents=None
    )
    entry_id = await _make_time_entry(ctx["agency_id"], ctx["brand_id"], ctx["member_id"], hours=1)
    await _invoice_and_approve(ctx["agency_id"], ctx["owner_id"], ctx["brand_id"], entry_id)

    async with AsyncSessionLocal() as session:
        result = await ProfitabilityService(session).get_brand_profitability(
            ctx["agency_id"], ctx["brand_id"]
        )

    c = result.currencies[0]
    assert c.invoiced_revenue_cents > 0
    assert c.internal_cost_cents is None
    assert c.gross_profit_cents is None
    assert c.gross_margin_pct is None
    assert c.margin_missing_reason == "cost_rate_eksik"


# ── Missing billing rate (forward-looking estimate) ─────────────────────────


async def test_brief_estimated_missing_billing_rate_flags_correctly() -> None:
    ctx = await _seed_agency_brand(
        "MissingBilling1", hourly_rate_cents=None, cost_rate_cents=20_000
    )
    brief_id = await _make_brief(
        ctx["agency_id"], ctx["brand_id"], ctx["owner_id"], estimated_hours=10
    )

    async with AsyncSessionLocal() as session:
        result = await ProfitabilityService(session).get_brief_profitability(
            ctx["agency_id"], brief_id
        )

    assert result.estimated is not None
    assert result.estimated.billing_rate_missing is True
    assert result.estimated.revenue_cents is None
    assert result.estimated.margin_missing_reason == "fiyatlandirma_eksik"


async def test_brief_without_estimated_hours_has_no_estimate_block() -> None:
    ctx = await _seed_agency_brand("NoEstimate1")
    brief_id = await _make_brief(ctx["agency_id"], ctx["brand_id"], ctx["owner_id"])

    async with AsyncSessionLocal() as session:
        result = await ProfitabilityService(session).get_brief_profitability(
            ctx["agency_id"], brief_id
        )
    assert result.estimated is None
    assert result.realized == []


# ── Zero revenue: no crash, margin null, never "0%" ─────────────────────────


async def test_brand_zero_revenue_no_crash_margin_is_null_not_zero_percent() -> None:
    ctx = await _seed_agency_brand("ZeroRevenue1", hourly_rate_cents=50_000, cost_rate_cents=20_000)
    # No invoices, no time entries at all.

    async with AsyncSessionLocal() as session:
        result = await ProfitabilityService(session).get_brand_profitability(
            ctx["agency_id"], ctx["brand_id"]
        )

    assert len(result.currencies) == 1
    c = result.currencies[0]
    assert c.currency == "TRY"
    assert c.invoiced_revenue_cents == 0
    assert c.gross_profit_cents == 0  # a real, known, zero-minus-zero value
    assert c.gross_margin_pct is None  # undefined at zero revenue — never "0%"
    assert c.margin_missing_reason is None  # this is "no data", not "missing rate"


async def test_agency_overview_with_no_brands_or_data_does_not_crash() -> None:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        agency = Agency(id=uuid.uuid4(), name="Empty Agency", slug=f"empty-{suffix}")
        session.add(agency)
        await session.commit()
        agency_id = agency.id

    async with AsyncSessionLocal() as session:
        result = await ProfitabilityService(session).get_agency_overview(agency_id)
    assert result.currencies == []
    assert result.risk_flags == []


# ── Multi-currency safety: never summed across currencies ──────────────────


async def test_agency_overview_never_sums_across_currencies() -> None:
    ctx_try = await _seed_agency_brand(
        "MultiCcy1", currency="TRY", hourly_rate_cents=50_000, cost_rate_cents=20_000
    )
    ctx_usd = await _seed_agency_brand(
        "MultiCcy1USD",
        currency="USD",
        hourly_rate_cents=100,
        cost_rate_cents=40,
        agency_id=ctx_try["agency_id"],
    )

    entry_try = await _make_time_entry(
        ctx_try["agency_id"], ctx_try["brand_id"], ctx_try["member_id"], hours=2
    )
    entry_usd = await _make_time_entry(
        ctx_usd["agency_id"], ctx_usd["brand_id"], ctx_usd["member_id"], hours=3
    )
    await _invoice_and_approve(
        ctx_try["agency_id"], ctx_try["owner_id"], ctx_try["brand_id"], entry_try
    )
    await _invoice_and_approve(
        ctx_usd["agency_id"], ctx_usd["owner_id"], ctx_usd["brand_id"], entry_usd
    )

    async with AsyncSessionLocal() as session:
        overview = await ProfitabilityService(session).get_agency_overview(ctx_try["agency_id"])

    by_currency = {c.currency: c for c in overview.currencies}
    assert set(by_currency.keys()) == {"TRY", "USD"}
    # TRY: 2h * 50000 = 100000 subtotal, +20% tax = 120000 total.
    assert by_currency["TRY"].invoiced_revenue_cents == 120_000
    # USD: 3h * 100 = 300 subtotal, +20% tax = 360 total.
    assert by_currency["USD"].invoiced_revenue_cents == 360
    # No field anywhere blends the two currencies into one number.
    assert not hasattr(overview, "total_revenue_cents")
    assert not hasattr(overview, "blended_revenue_cents")
    assert not any(hasattr(c, "total_revenue_cents") for c in overview.currencies)


async def test_brand_currency_matches_its_own_invoices_only() -> None:
    """A brand's own currency breakdown must reflect only its own invoices —
    proven by seeding a second, differently-currencied brand under the same
    agency and confirming it doesn't leak into the first brand's numbers."""
    ctx_try = await _seed_agency_brand(
        "OwnCcy1", currency="TRY", hourly_rate_cents=50_000, cost_rate_cents=20_000
    )
    ctx_usd = await _seed_agency_brand(
        "OwnCcy1USD",
        currency="USD",
        hourly_rate_cents=100,
        cost_rate_cents=40,
        agency_id=ctx_try["agency_id"],
    )
    entry_try = await _make_time_entry(
        ctx_try["agency_id"], ctx_try["brand_id"], ctx_try["member_id"], hours=1
    )
    entry_usd = await _make_time_entry(
        ctx_usd["agency_id"], ctx_usd["brand_id"], ctx_usd["member_id"], hours=1
    )
    await _invoice_and_approve(
        ctx_try["agency_id"], ctx_try["owner_id"], ctx_try["brand_id"], entry_try
    )
    await _invoice_and_approve(
        ctx_usd["agency_id"], ctx_usd["owner_id"], ctx_usd["brand_id"], entry_usd
    )

    async with AsyncSessionLocal() as session:
        brand_try_result = await ProfitabilityService(session).get_brand_profitability(
            ctx_try["agency_id"], ctx_try["brand_id"]
        )
    currencies = [c.currency for c in brand_try_result.currencies]
    assert currencies == ["TRY"]
    assert brand_try_result.currencies[0].invoiced_revenue_cents == 60_000  # 1h*50000 +20% tax

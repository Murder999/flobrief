"""E2E fixture for e2e/profitability-flow.spec.ts.

Creates one Agency + owner (the only role with COST_RATE_VIEW, needed to see
cost/margin fields at all) and two Brands, each with an active hourly
CommercialTerms and one directly-inserted "sent" ClientInvoice + line so the
brand-level profitability read has real, already-invoiced revenue to
aggregate without needing to drive the whole draft->send lifecycle again
(that's already covered end-to-end by invoice-lifecycle-flow.spec.ts):

  - Brand C ("E2E Profitability Brand With Cost"): the line carries a real
    cost_rate_snapshot_cents -> ProfitabilityService can compute a genuine
    cost/gross-profit/margin for it.
  - Brand D ("E2E Profitability Brand No Cost"): the line's
    cost_rate_snapshot_cents is left NULL -> ProfitabilityService must flag
    this scope's cost/margin as incomplete (margin_missing_reason =
    "cost_rate_eksik", rendered by the frontend as "Maliyet oranı eksik"),
    never fabricate a 0% margin or a blank cell.

Two modes:
  python e2e_seed_profitability.py seed            -> prints E2E_* env vars
  python e2e_seed_profitability.py cleanup <agency_id>

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production" -- mirrors e2e_seed_time_tracking.py.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.agency import Agency  # noqa: E402
from app.models.agency_member import AgencyMember  # noqa: E402
from app.models.brand import Brand  # noqa: E402
from app.models.client_invoice import ClientInvoice, ClientInvoiceLine  # noqa: E402
from app.models.commercial_terms import CommercialTerms  # noqa: E402
from app.models.enums import (  # noqa: E402
    AgencyMemberRole,
    AgencyMemberStatus,
    AgencyStatus,
    BrandStatus,
    UserType,
)
from app.models.user import User  # noqa: E402

OWNER_EMAIL = "flobrief-e2e-profitability-owner@example.com"
PASSWORD = "E2eTest1234!"
BRAND_WITH_COST_NAME = "E2E Profitability Brand With Cost"
BRAND_NO_COST_NAME = "E2E Profitability Brand No Cost"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _assert_local_test_database() -> None:
    host = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing to run: DATABASE_URL host {host!r} is not a local host {_LOCAL_HOSTS}."
        )
    if settings.is_production:
        raise RuntimeError("Refusing to run: APP_ENV=production.")


async def cleanup_by_email() -> None:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == OWNER_EMAIL))).scalar_one_or_none()
        if user is not None:
            member = (await db.execute(
                select(AgencyMember).where(AgencyMember.user_id == user.id)
            )).scalar_one_or_none()
            if member is not None:
                agency = await db.get(Agency, member.agency_id)
                if agency is not None:
                    await db.delete(agency)
                brands = (await db.execute(
                    select(Brand).where(Brand.agency_id == member.agency_id)
                )).scalars().all()
                for brand in brands:
                    await db.delete(brand)
        await db.commit()

        user = (await db.execute(select(User).where(User.email == OWNER_EMAIL))).scalar_one_or_none()
        if user is not None:
            await db.delete(user)
        await db.commit()


async def cleanup_by_agency_id(agency_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        agency = await db.get(Agency, agency_id)
        if agency is not None:
            await db.delete(agency)  # cascades agency_members/client_invoices/...
        brands = (await db.execute(
            select(Brand).where(Brand.agency_id == agency_id)
        )).scalars().all()
        for brand in brands:
            await db.delete(brand)
        await db.commit()

        user = (await db.execute(select(User).where(User.email == OWNER_EMAIL))).scalar_one_or_none()
        if user is not None:
            await db.delete(user)
        await db.commit()


async def seed_db() -> uuid.UUID:
    now = datetime.now(UTC)
    today = now.date()
    async with AsyncSessionLocal() as db:
        agency = Agency(
            id=uuid.uuid4(), name="E2E Profitability Agency",
            slug=f"e2e-profitability-agency-{uuid.uuid4().hex[:8]}",
            status=AgencyStatus.ACTIVE.value,
        )
        brand_with_cost = Brand(
            id=uuid.uuid4(), agency_id=agency.id, name=BRAND_WITH_COST_NAME,
            slug=f"e2e-prof-cost-{uuid.uuid4().hex[:8]}", status=BrandStatus.ACTIVE.value,
            currency="TRY",
        )
        brand_no_cost = Brand(
            id=uuid.uuid4(), agency_id=agency.id, name=BRAND_NO_COST_NAME,
            slug=f"e2e-prof-nocost-{uuid.uuid4().hex[:8]}", status=BrandStatus.ACTIVE.value,
            currency="TRY",
        )
        db.add_all([agency, brand_with_cost, brand_no_cost])

        owner = User(
            id=uuid.uuid4(), email=OWNER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="E2E Profitability Owner", user_type=UserType.AGENCY_USER.value,
            is_active=True, is_verified=True,
        )
        db.add(owner)
        await db.flush()

        db.add(AgencyMember(
            id=uuid.uuid4(), agency_id=agency.id, user_id=owner.id,
            role=AgencyMemberRole.OWNER.value, status=AgencyMemberStatus.ACTIVE.value,
        ))

        terms_with_cost = CommercialTerms(
            id=uuid.uuid4(), agency_id=agency.id, brand_id=brand_with_cost.id,
            billing_model="hourly", currency="TRY", hourly_rate_cents=100_000,
            payment_terms_days=30, tax_rate_bps=2000,
            valid_from=today - timedelta(days=60), active=True, created_by_id=owner.id,
        )
        terms_no_cost = CommercialTerms(
            id=uuid.uuid4(), agency_id=agency.id, brand_id=brand_no_cost.id,
            billing_model="hourly", currency="TRY", hourly_rate_cents=100_000,
            payment_terms_days=30, tax_rate_bps=2000,
            valid_from=today - timedelta(days=60), active=True, created_by_id=owner.id,
        )
        db.add_all([terms_with_cost, terms_no_cost])
        await db.flush()

        invoice_with_cost = ClientInvoice(
            id=uuid.uuid4(), agency_id=agency.id, brand_id=brand_with_cost.id,
            commercial_terms_id=terms_with_cost.id,
            invoice_number=f"E2E-PROF-COST-{uuid.uuid4().hex[:6]}",
            document_type="draft_invoice", issue_date=today, due_date=today + timedelta(days=30),
            currency="TRY", subtotal_cents=500_000, discount_cents=0, tax_cents=100_000,
            total_cents=600_000, amount_paid_cents=0, status="sent",
            created_by_id=owner.id, approved_by_id=owner.id, approved_at=now, sent_at=now,
        )
        invoice_no_cost = ClientInvoice(
            id=uuid.uuid4(), agency_id=agency.id, brand_id=brand_no_cost.id,
            commercial_terms_id=terms_no_cost.id,
            invoice_number=f"E2E-PROF-NOCOST-{uuid.uuid4().hex[:6]}",
            document_type="draft_invoice", issue_date=today, due_date=today + timedelta(days=30),
            currency="TRY", subtotal_cents=400_000, discount_cents=0, tax_cents=80_000,
            total_cents=480_000, amount_paid_cents=0, status="sent",
            created_by_id=owner.id, approved_by_id=owner.id, approved_at=now, sent_at=now,
        )
        db.add_all([invoice_with_cost, invoice_no_cost])
        await db.flush()

        db.add_all([
            ClientInvoiceLine(
                id=uuid.uuid4(), invoice_id=invoice_with_cost.id, source_type="time_entry",
                description="E2E invoiced hours (cost rate configured)", quantity=5, unit="saat",
                unit_price_cents=100_000, tax_rate_bps=2000, discount_cents=0,
                subtotal_cents=500_000, tax_cents=100_000, total_cents=600_000,
                billing_rate_snapshot_cents=100_000, cost_rate_snapshot_cents=40_000,
            ),
            ClientInvoiceLine(
                id=uuid.uuid4(), invoice_id=invoice_no_cost.id, source_type="time_entry",
                description="E2E invoiced hours (no cost rate configured)", quantity=4, unit="saat",
                unit_price_cents=100_000, tax_rate_bps=2000, discount_cents=0,
                subtotal_cents=400_000, tax_cents=80_000, total_cents=480_000,
                billing_rate_snapshot_cents=100_000, cost_rate_snapshot_cents=None,
            ),
        ])
        await db.commit()

        return agency.id


async def main() -> None:
    _assert_local_test_database()

    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if mode == "cleanup":
        if len(sys.argv) > 2:
            await cleanup_by_agency_id(uuid.UUID(sys.argv[2]))
        else:
            await cleanup_by_email()
        print("cleaned up")
        return

    await cleanup_by_email()
    agency_id = await seed_db()
    print("E2E_OWNER_EMAIL=" + OWNER_EMAIL)
    print("E2E_PASSWORD=" + PASSWORD)
    print("E2E_BRAND_WITH_COST_NAME=" + BRAND_WITH_COST_NAME)
    print("E2E_BRAND_NO_COST_NAME=" + BRAND_NO_COST_NAME)
    print("__AGENCY_ID__=" + str(agency_id))


if __name__ == "__main__":
    asyncio.run(main())

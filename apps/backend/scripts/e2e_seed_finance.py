"""E2E fixture shared by e2e/invoice-lifecycle-flow.spec.ts and
e2e/brand-portal-invoice-isolation.spec.ts (each calls `seed`/`cleanup`
independently -- safe because playwright.config.ts runs with
`fullyParallel: false, workers: 1`, so the two spec files never race on the
shared fixture emails).

Creates one Agency with an owner (AgencyMemberRole.OWNER -> INVOICE_CREATE/
APPROVE/VOID, PAYMENT_MANAGE, COST_RATE_*, COMMERCIAL_TERMS_MANAGE), two
Brands each with their own brand-portal user:
  - Brand A: an active hourly CommercialTerms (1000 TRY/hour, 20% KDV), a
    MemberCostRate for the owner set to a deliberately distinctive value
    (13337.00 TRY/hour) so brand-portal-invoice-isolation.spec.ts can grep
    the rendered brand-portal DOM for its literal absence, two locked+
    billable (not yet invoiced) TimeEntry rows totalling 3 hours for
    invoice-lifecycle-flow.spec.ts to select on /dashboard/finance/
    billable-time, one directly-inserted "sent" ClientInvoice (+ line
    carrying the same distinctive cost snapshot) so the isolation spec has
    real visible data without going through the full lifecycle itself, and
    one directly-inserted "draft" ClientInvoice to prove drafts never reach
    the brand portal.
  - Brand B: one directly-inserted "sent" ClientInvoice with a distinct
    invoice number, used as the cross-tenant IDOR target -- Brand A's
    brand-portal user must be refused when navigating directly to it.

Two modes:
  python e2e_seed_finance.py seed            -> prints E2E_* env vars
  python e2e_seed_finance.py cleanup <agency_id>

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
from app.models.brand_member import BrandMember  # noqa: E402
from app.models.client_invoice import ClientInvoice, ClientInvoiceLine  # noqa: E402
from app.models.commercial_terms import CommercialTerms, MemberCostRate  # noqa: E402
from app.models.enums import (  # noqa: E402
    AgencyMemberRole,
    AgencyMemberStatus,
    AgencyStatus,
    BrandMemberRole,
    BrandMemberStatus,
    BrandStatus,
    UserType,
)
from app.models.time_entry import TimeEntry  # noqa: E402
from app.models.user import User  # noqa: E402

OWNER_EMAIL = "flobrief-e2e-finance-owner@example.com"
BRAND_A_EMAIL = "flobrief-e2e-finance-brand-a@example.com"
BRAND_B_EMAIL = "flobrief-e2e-finance-brand-b@example.com"
PASSWORD = "E2eTest1234!"

# Deliberately distinctive so a substring grep of the rendered brand-portal
# DOM proves the absence of internal cost figures, not just an "empty
# looking" page.
DISTINCTIVE_COST_RATE_CENTS = 1_333_700  # 13337.00 TRY/hour
HOURLY_RATE_CENTS = 100_000  # 1000.00 TRY/hour

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _assert_local_test_database() -> None:
    host = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing to run: DATABASE_URL host {host!r} is not a local host {_LOCAL_HOSTS}."
        )
    if settings.is_production:
        raise RuntimeError("Refusing to run: APP_ENV=production.")


_ALL_EMAILS = (OWNER_EMAIL, BRAND_A_EMAIL, BRAND_B_EMAIL)


async def cleanup_by_email() -> None:
    async with AsyncSessionLocal() as db:
        for email in _ALL_EMAILS:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                continue
            member = (
                await db.execute(select(AgencyMember).where(AgencyMember.user_id == user.id))
            ).scalar_one_or_none()
            if member is not None:
                agency = await db.get(Agency, member.agency_id)
                if agency is not None:
                    await db.delete(agency)
                brands = (
                    (await db.execute(select(Brand).where(Brand.agency_id == member.agency_id)))
                    .scalars()
                    .all()
                )
                for brand in brands:
                    await db.delete(brand)
        await db.commit()

        for email in _ALL_EMAILS:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


async def cleanup_by_agency_id(agency_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        agency = await db.get(Agency, agency_id)
        if agency is not None:
            await db.delete(agency)  # cascades agency_members/time_entries/client_invoices/...
        brands = (
            (await db.execute(select(Brand).where(Brand.agency_id == agency_id))).scalars().all()
        )
        for brand in brands:
            await db.delete(brand)
        await db.commit()

        for email in _ALL_EMAILS:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


async def seed_db() -> dict[str, uuid.UUID]:
    now = datetime.now(UTC)
    today = now.date()
    async with AsyncSessionLocal() as db:
        agency = Agency(
            id=uuid.uuid4(),
            name="E2E Finance Agency",
            slug=f"e2e-finance-agency-{uuid.uuid4().hex[:8]}",
            status=AgencyStatus.ACTIVE.value,
        )
        brand_a = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name="E2E Finance Brand A",
            slug=f"e2e-finance-brand-a-{uuid.uuid4().hex[:8]}",
            status=BrandStatus.ACTIVE.value,
            currency="TRY",
        )
        brand_b = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name="E2E Finance Brand B",
            slug=f"e2e-finance-brand-b-{uuid.uuid4().hex[:8]}",
            status=BrandStatus.ACTIVE.value,
            currency="TRY",
        )
        db.add_all([agency, brand_a, brand_b])

        owner = User(
            id=uuid.uuid4(),
            email=OWNER_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Finance Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        brand_a_user = User(
            id=uuid.uuid4(),
            email=BRAND_A_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Finance Brand A Owner",
            user_type=UserType.BRAND_USER.value,
            is_active=True,
            is_verified=True,
        )
        brand_b_user = User(
            id=uuid.uuid4(),
            email=BRAND_B_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Finance Brand B Owner",
            user_type=UserType.BRAND_USER.value,
            is_active=True,
            is_verified=True,
        )
        db.add_all([owner, brand_a_user, brand_b_user])
        await db.flush()

        db.add_all(
            [
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=owner.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                BrandMember(
                    id=uuid.uuid4(),
                    brand_id=brand_a.id,
                    user_id=brand_a_user.id,
                    role=BrandMemberRole.BRAND_OWNER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                ),
                BrandMember(
                    id=uuid.uuid4(),
                    brand_id=brand_b.id,
                    user_id=brand_b_user.id,
                    role=BrandMemberRole.BRAND_OWNER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                ),
            ]
        )

        commercial_terms = CommercialTerms(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand_a.id,
            billing_model="hourly",
            currency="TRY",
            hourly_rate_cents=HOURLY_RATE_CENTS,
            payment_terms_days=30,
            tax_rate_bps=2000,
            valid_from=today - timedelta(days=60),
            active=True,
            created_by_id=owner.id,
        )
        cost_rate = MemberCostRate(
            id=uuid.uuid4(),
            agency_id=agency.id,
            user_id=owner.id,
            currency="TRY",
            hourly_cost_cents=DISTINCTIVE_COST_RATE_CENTS,
            valid_from=today - timedelta(days=60),
            active=True,
            created_by_id=owner.id,
        )
        db.add_all([commercial_terms, cost_rate])
        await db.flush()

        entry_1 = TimeEntry(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand_a.id,
            user_id=owner.id,
            category="design",
            description="E2E billable work block 1",
            started_at=now - timedelta(hours=3),
            ended_at=now - timedelta(hours=1),
            duration_seconds=7200,
            billable=True,
            source="manual",
            locked=True,
        )
        entry_2 = TimeEntry(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand_a.id,
            user_id=owner.id,
            category="design",
            description="E2E billable work block 2",
            started_at=now - timedelta(hours=1),
            ended_at=now,
            duration_seconds=3600,
            billable=True,
            source="manual",
            locked=True,
        )
        db.add_all([entry_1, entry_2])

        sent_invoice_a = ClientInvoice(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand_a.id,
            commercial_terms_id=commercial_terms.id,
            invoice_number=f"E2E-SENT-A-{uuid.uuid4().hex[:6]}",
            document_type="draft_invoice",
            issue_date=today,
            due_date=today + timedelta(days=30),
            currency="TRY",
            subtotal_cents=300_000,
            discount_cents=0,
            tax_cents=60_000,
            total_cents=360_000,
            amount_paid_cents=0,
            status="sent",
            created_by_id=owner.id,
            approved_by_id=owner.id,
            approved_at=now,
            sent_at=now,
        )
        draft_invoice_a = ClientInvoice(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand_a.id,
            commercial_terms_id=commercial_terms.id,
            invoice_number=f"E2E-DRAFT-A-{uuid.uuid4().hex[:6]}",
            document_type="draft_invoice",
            issue_date=today,
            due_date=today + timedelta(days=30),
            currency="TRY",
            subtotal_cents=100_000,
            discount_cents=0,
            tax_cents=20_000,
            total_cents=120_000,
            amount_paid_cents=0,
            status="draft",
            created_by_id=owner.id,
        )
        sent_invoice_b = ClientInvoice(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand_b.id,
            invoice_number=f"E2E-SENT-B-{uuid.uuid4().hex[:6]}",
            document_type="draft_invoice",
            issue_date=today,
            due_date=today + timedelta(days=30),
            currency="TRY",
            subtotal_cents=200_000,
            discount_cents=0,
            tax_cents=40_000,
            total_cents=240_000,
            amount_paid_cents=0,
            status="sent",
            created_by_id=owner.id,
            approved_by_id=owner.id,
            approved_at=now,
            sent_at=now,
        )
        db.add_all([sent_invoice_a, draft_invoice_a, sent_invoice_b])
        await db.flush()

        db.add(
            ClientInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=sent_invoice_a.id,
                source_type="manual",
                description="E2E sent invoice line",
                quantity=3,
                unit="saat",
                unit_price_cents=HOURLY_RATE_CENTS,
                tax_rate_bps=2000,
                discount_cents=0,
                subtotal_cents=300_000,
                tax_cents=60_000,
                total_cents=360_000,
                billing_rate_snapshot_cents=HOURLY_RATE_CENTS,
                cost_rate_snapshot_cents=DISTINCTIVE_COST_RATE_CENTS,
            )
        )
        await db.commit()

        return {
            "agency_id": agency.id,
            "brand_a_id": brand_a.id,
            "brand_b_id": brand_b.id,
            "owner_id": owner.id,
            "sent_invoice_a_id": sent_invoice_a.id,
            "draft_invoice_a_id": draft_invoice_a.id,
            "sent_invoice_b_id": sent_invoice_b.id,
        }


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
    ids = await seed_db()
    print("E2E_OWNER_EMAIL=" + OWNER_EMAIL)
    print("E2E_BRAND_A_EMAIL=" + BRAND_A_EMAIL)
    print("E2E_BRAND_B_EMAIL=" + BRAND_B_EMAIL)
    print("E2E_PASSWORD=" + PASSWORD)
    print("E2E_BRAND_A_ID=" + str(ids["brand_a_id"]))
    print("E2E_BRAND_B_ID=" + str(ids["brand_b_id"]))
    print("E2E_SENT_INVOICE_A_ID=" + str(ids["sent_invoice_a_id"]))
    print("E2E_DRAFT_INVOICE_A_ID=" + str(ids["draft_invoice_a_id"]))
    print("E2E_SENT_INVOICE_B_ID=" + str(ids["sent_invoice_b_id"]))
    print("__AGENCY_ID__=" + str(ids["agency_id"]))


if __name__ == "__main__":
    asyncio.run(main())

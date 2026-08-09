"""CSV-injection guard tests (plan §12): a cell value starting with
`=`/`+`/`-`/`@` must be escaped with a leading `'` before it is written to
an exported CSV, both at the shared `escape_csv_cell` helper level and at
the `ClientInvoiceService.export_csv` integration level — invoice line
descriptions are free-text, user-entered fields and are the concrete attack
surface this guards."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta

from app.core.csv_safety import escape_csv_cell
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.commercial_terms import CommercialTerms
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.schemas.client_invoice import ClientInvoiceDraftCreate, ManualInvoiceLineInput
from app.services.client_invoice_service import ClientInvoiceService

TODAY = datetime.now(UTC).date()


# ── Unit tests: the shared helper ───────────────────────────────────────────


def test_escape_csv_cell_prefixes_equals_sign() -> None:
    assert escape_csv_cell("=cmd|'/c calc'!A1") == "'=cmd|'/c calc'!A1"


def test_escape_csv_cell_prefixes_plus_sign() -> None:
    assert escape_csv_cell("+1+1") == "'+1+1"


def test_escape_csv_cell_prefixes_minus_sign() -> None:
    assert escape_csv_cell("-2+3") == "'-2+3"


def test_escape_csv_cell_prefixes_at_sign() -> None:
    assert escape_csv_cell("@SUM(A1:A9)") == "'@SUM(A1:A9)"


def test_escape_csv_cell_leaves_safe_text_unchanged() -> None:
    assert escape_csv_cell("Design work for Q1") == "Design work for Q1"


def test_escape_csv_cell_handles_empty_string() -> None:
    assert escape_csv_cell("") == ""


def test_escape_csv_cell_does_not_over_escape_mid_string_special_chars() -> None:
    # The dangerous-prefix rule only cares about the FIRST character.
    assert escape_csv_cell("Total = 100") == "Total = 100"


# ── Integration: ClientInvoiceService.export_csv ────────────────────────────


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


async def _seed_invoice_with_malicious_manual_line(label: str, description: str) -> dict:
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
        await session.flush()
        session.add(
            AgencyMember(
                id=uuid.uuid4(),
                agency_id=agency.id,
                user_id=owner.id,
                role=AgencyMemberRole.OWNER.value,
                status=AgencyMemberStatus.ACTIVE.value,
            )
        )
        session.add(
            CommercialTerms(
                id=uuid.uuid4(),
                agency_id=agency.id,
                brand_id=brand.id,
                billing_model="hourly",
                currency="TRY",
                hourly_rate_cents=50_000,
                payment_terms_days=30,
                tax_rate_bps=0,
                valid_from=TODAY - timedelta(days=10),
                active=True,
            )
        )
        await session.commit()
        agency_id, brand_id, owner_id = agency.id, brand.id, owner.id

    async with AsyncSessionLocal() as session:
        invoice = await ClientInvoiceService(session).generate_draft(
            agency_id,
            owner_id,
            ClientInvoiceDraftCreate(
                brand_id=brand_id,
                manual_lines=[
                    ManualInvoiceLineInput(
                        description=description,
                        quantity=1,
                        unit="adet",
                        unit_price_cents=1000,
                    )
                ],
            ),
        )
    return {"agency_id": agency_id, "invoice_id": invoice.id}


async def test_export_csv_escapes_formula_leading_description() -> None:
    ctx = await _seed_invoice_with_malicious_manual_line("CsvInj1", "=cmd|' /c calc'!A1")
    async with AsyncSessionLocal() as session:
        csv_bytes = await ClientInvoiceService(session).export_csv(
            ctx["agency_id"], ctx["invoice_id"]
        )

    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    data_row = rows[1]
    description_cell = data_row[1]
    assert description_cell.startswith(
        "'="
    ), f"formula-leading description not escaped in exported CSV: {description_cell!r}"


async def test_export_csv_escapes_at_sign_leading_description() -> None:
    ctx = await _seed_invoice_with_malicious_manual_line("CsvInj2", "@SUM(1+1)*cmd")
    async with AsyncSessionLocal() as session:
        csv_bytes = await ClientInvoiceService(session).export_csv(
            ctx["agency_id"], ctx["invoice_id"]
        )

    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    description_cell = rows[1][1]
    assert description_cell.startswith("'@")


async def test_export_csv_leaves_normal_description_unescaped() -> None:
    ctx = await _seed_invoice_with_malicious_manual_line("CsvInj3", "Fotograf cekimi ucreti")
    async with AsyncSessionLocal() as session:
        csv_bytes = await ClientInvoiceService(session).export_csv(
            ctx["agency_id"], ctx["invoice_id"]
        )

    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    description_cell = rows[1][1]
    assert description_cell == "Fotograf cekimi ucreti"
    assert not description_cell.startswith("'")

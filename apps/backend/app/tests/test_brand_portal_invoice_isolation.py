"""Brand-portal invoice view tests (plan §9/§12/§13, closes the Phase-4
gap): a brand-portal user sees ONLY their own brand's non-draft/
non-pending-approval/non-cancelled invoices — never another brand's
invoices (tenant/IDOR), never an in-progress draft, and the response schema
genuinely has no cost-rate/margin field (inspected on the Pydantic model
itself, not just absent from a particular HTTP response)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.db.session import AsyncSessionLocal
from app.models.client_invoice import ClientInvoice, ClientInvoiceLine
from app.tests.conftest import brand_headers

TODAY = datetime.now(UTC).date()


async def _make_invoice(
    agency_id: uuid.UUID, brand_id: uuid.UUID, status: str, *, label: str
) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        invoice = ClientInvoice(
            id=uuid.uuid4(),
            agency_id=agency_id,
            brand_id=brand_id,
            invoice_number=f"{label}-{uuid.uuid4().hex[:8]}",
            document_type="draft_invoice",
            issue_date=TODAY,
            due_date=TODAY,
            currency="TRY",
            subtotal_cents=100_000,
            discount_cents=0,
            tax_cents=20_000,
            total_cents=120_000,
            amount_paid_cents=0,
            status=status,
        )
        session.add(invoice)
        await session.commit()
        return invoice.id


async def _add_line(
    invoice_id: uuid.UUID,
    *,
    description: str = "Sosyal medya yönetimi — Temmuz",
    quantity: float = 1.0,
    unit_price_cents: int = 100_000,
) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        line = ClientInvoiceLine(
            id=uuid.uuid4(),
            invoice_id=invoice_id,
            source_type="manual",
            description=description,
            quantity=quantity,
            unit="adet",
            unit_price_cents=unit_price_cents,
            tax_rate_bps=2000,
            discount_cents=0,
            subtotal_cents=int(quantity * unit_price_cents),
            tax_cents=int(quantity * unit_price_cents * 0.20),
            total_cents=int(quantity * unit_price_cents * 1.20),
            billing_rate_snapshot_cents=unit_price_cents,
            cost_rate_snapshot_cents=int(unit_price_cents * 0.6),
            service_period_start=TODAY,
            service_period_end=TODAY,
        )
        session.add(line)
        await session.commit()
        return line.id


# ── Schema-level guarantee: no cost/margin field exists at all ─────────────


def test_brand_invoice_read_schema_has_no_cost_or_margin_field() -> None:
    from app.schemas.brand_finance import BrandInvoiceRead

    field_names = set(BrandInvoiceRead.model_fields.keys())
    forbidden = {
        "cost_rate_snapshot_cents",
        "billing_rate_snapshot_cents",
        "commercial_terms_id",
        "created_by_id",
        "approved_by_id",
    }
    leaked = field_names & forbidden
    assert not leaked, f"BrandInvoiceRead leaks internal fields: {leaked}"


# ── Visibility: status filtering ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_brand_user_sees_only_non_draft_non_cancelled_invoices(client, tenants) -> None:
    tenant_a, _ = tenants
    draft_id = await _make_invoice(tenant_a.agency_id, tenant_a.brand_id, "draft", label="DRAFT")
    pending_id = await _make_invoice(
        tenant_a.agency_id, tenant_a.brand_id, "pending_approval", label="PENDING"
    )
    cancelled_id = await _make_invoice(
        tenant_a.agency_id, tenant_a.brand_id, "cancelled", label="CANCELLED"
    )
    sent_id = await _make_invoice(tenant_a.agency_id, tenant_a.brand_id, "sent", label="SENT")
    paid_id = await _make_invoice(tenant_a.agency_id, tenant_a.brand_id, "paid", label="PAID")

    resp = await client.get(
        "/api/v1/brand-portal/invoices",
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert resp.status_code == 200
    visible_ids = {item["id"] for item in resp.json()}

    assert str(sent_id) in visible_ids
    assert str(paid_id) in visible_ids
    assert str(draft_id) not in visible_ids
    assert str(pending_id) not in visible_ids
    assert str(cancelled_id) not in visible_ids


@pytest.mark.asyncio
async def test_brand_user_cannot_download_pdf_for_draft_invoice(client, tenants) -> None:
    tenant_a, _ = tenants
    draft_id = await _make_invoice(tenant_a.agency_id, tenant_a.brand_id, "draft", label="DRAFTPDF")
    resp = await client.get(
        f"/api/v1/brand-portal/invoices/{draft_id}/pdf",
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_brand_user_can_download_pdf_for_sent_invoice(client, tenants) -> None:
    tenant_a, _ = tenants
    sent_id = await _make_invoice(tenant_a.agency_id, tenant_a.brand_id, "sent", label="SENTPDF")
    resp = await client.get(
        f"/api/v1/brand-portal/invoices/{sent_id}/pdf",
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


# ── Tenant isolation / IDOR ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_brand_user_cannot_see_another_brands_invoices(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    other_sent_id = await _make_invoice(
        tenant_b.agency_id, tenant_b.brand_id, "sent", label="OTHERBRAND"
    )

    resp = await client.get(
        "/api/v1/brand-portal/invoices",
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert resp.status_code == 200
    visible_ids = {item["id"] for item in resp.json()}
    assert str(other_sent_id) not in visible_ids


@pytest.mark.asyncio
async def test_brand_user_cannot_fetch_another_brands_invoice_pdf_by_id(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    other_sent_id = await _make_invoice(
        tenant_b.agency_id, tenant_b.brand_id, "sent", label="OTHERPDF"
    )
    resp = await client.get(
        f"/api/v1/brand-portal/invoices/{other_sent_id}/pdf",
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agency_side_jwt_cannot_reach_brand_portal_invoice_endpoint(client, tenants) -> None:
    """Mirrors the existing `brand_user_jwt_cannot_view_capacity_report`
    pattern in reverse: an agency-side JWT presented to the brand-portal
    dependency must be rejected, not silently treated as some brand."""
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/brand-portal/invoices",
        headers={"Authorization": f"Bearer {tenant_a.agency_token}"},
    )
    assert resp.status_code == 403


# ── HTTP response never contains a cost field either ────────────────────────


@pytest.mark.asyncio
async def test_http_response_never_contains_cost_rate_text(client, tenants) -> None:
    tenant_a, _ = tenants
    await _make_invoice(tenant_a.agency_id, tenant_a.brand_id, "sent", label="COSTCHECK")
    resp = await client.get(
        "/api/v1/brand-portal/invoices",
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert resp.status_code == 200
    assert "cost_rate_snapshot_cents" not in resp.text
    assert "billing_rate_snapshot_cents" not in resp.text


# ── Invoice detail: service line items ──────────────────────────────────────


def test_brand_invoice_line_read_schema_has_no_cost_or_margin_field() -> None:
    from app.schemas.brand_finance import BrandInvoiceLineRead

    field_names = set(BrandInvoiceLineRead.model_fields.keys())
    forbidden = {
        "cost_rate_snapshot_cents",
        "billing_rate_snapshot_cents",
        "invoice_id",
        "source_type",
        "source_id",
    }
    leaked = field_names & forbidden
    assert not leaked, f"BrandInvoiceLineRead leaks internal fields: {leaked}"
    assert field_names == {
        "id",
        "description",
        "quantity",
        "unit",
        "unit_price_cents",
        "tax_rate_bps",
        "discount_cents",
        "subtotal_cents",
        "tax_cents",
        "total_cents",
        "service_period_start",
        "service_period_end",
    }


@pytest.mark.asyncio
async def test_brand_user_sees_lines_for_sent_invoice_detail(client, tenants) -> None:
    tenant_a, _ = tenants
    sent_id = await _make_invoice(tenant_a.agency_id, tenant_a.brand_id, "sent", label="DETAIL")
    await _add_line(
        sent_id, description="Sosyal medya yönetimi", quantity=1.0, unit_price_cents=100_000
    )

    resp = await client.get(
        f"/api/v1/brand-portal/invoices/{sent_id}",
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(sent_id)
    assert len(body["lines"]) == 1
    line = body["lines"][0]
    assert line["description"] == "Sosyal medya yönetimi"
    assert line["quantity"] == 1.0
    assert line["unit_price_cents"] == 100_000
    # Totals in the detail response must reconcile with the summed lines.
    assert sum(item["total_cents"] for item in body["lines"]) == line["total_cents"]
    assert "cost_rate_snapshot_cents" not in resp.text
    assert "billing_rate_snapshot_cents" not in resp.text


@pytest.mark.asyncio
async def test_brand_user_cannot_see_draft_invoice_detail(client, tenants) -> None:
    tenant_a, _ = tenants
    draft_id = await _make_invoice(
        tenant_a.agency_id, tenant_a.brand_id, "draft", label="DRAFTDETAIL"
    )
    resp = await client.get(
        f"/api/v1/brand-portal/invoices/{draft_id}",
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_brand_user_cannot_see_another_brands_invoice_detail(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    other_sent_id = await _make_invoice(
        tenant_b.agency_id, tenant_b.brand_id, "sent", label="OTHERDETAIL"
    )
    await _add_line(other_sent_id)

    resp = await client.get(
        f"/api/v1/brand-portal/invoices/{other_sent_id}",
        headers=brand_headers(tenant_a.brand_manager_token),
    )
    assert resp.status_code == 404

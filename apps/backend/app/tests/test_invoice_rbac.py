"""RBAC coverage for the invoicing permission set (plan §8):
BILLING_TIME_VIEW, INVOICE_VIEW, INVOICE_CREATE, INVOICE_APPROVE,
INVOICE_VOID.

Verifies the plan's exact role table: Owner and Admin have the full invoice
lifecycle; Brand Manager has BILLING_TIME_VIEW/INVOICE_VIEW only (never
create/approve/void); Designer/Developer/Social Media Manager/Viewer have
none of the five; brand-portal JWTs cannot reach any agency-side finance
endpoint; and cross-tenant IDOR is blocked on both billable-time and invoice
list/detail endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency_member import AgencyMember
from app.models.commercial_terms import CommercialTerms
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.tests.conftest import agency_headers, brand_headers

TODAY = date.today()


async def _add_agency_member(agency_id: uuid.UUID, role: str) -> tuple[uuid.UUID, str]:
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"{role}-{uuid.uuid4().hex[:8]}@test.local",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name=f"Test {role}",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        session.add(
            AgencyMember(
                id=uuid.uuid4(),
                agency_id=agency_id,
                user_id=user.id,
                role=role,
                status=AgencyMemberStatus.ACTIVE.value,
            )
        )
        await session.commit()
        return user.id, create_access_token(str(user.id))


async def _seed_billing_prereqs(
    agency_id: uuid.UUID, brand_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID:
    """Active hourly `CommercialTerms` + one locked, billable `TimeEntry` —
    the minimum fixture for a permission-positive draft-invoice call."""
    async with AsyncSessionLocal() as session:
        session.add(
            CommercialTerms(
                id=uuid.uuid4(),
                agency_id=agency_id,
                brand_id=brand_id,
                billing_model="hourly",
                currency="TRY",
                hourly_rate_cents=50_000,
                payment_terms_days=30,
                tax_rate_bps=2000,
                valid_from=TODAY - timedelta(days=10),
                active=True,
            )
        )
        started = datetime.now(UTC) - timedelta(hours=3)
        entry = TimeEntry(
            id=uuid.uuid4(),
            agency_id=agency_id,
            brand_id=brand_id,
            user_id=user_id,
            category="design",
            started_at=started,
            ended_at=started + timedelta(hours=2),
            duration_seconds=7200,
            billable=True,
            source="manual",
            locked=True,
        )
        session.add(entry)
        await session.commit()
        return entry.id


def _draft_payload(brand_id: uuid.UUID, entry_id: uuid.UUID) -> dict:
    return {"brand_id": str(brand_id), "time_entry_ids": [str(entry_id)]}


# ------------------------------------------------------------------
# Owner / Admin: full lifecycle


@pytest.mark.asyncio
async def test_owner_can_run_full_invoice_lifecycle(client, tenants) -> None:
    tenant_a, _ = tenants
    owner_id, owner_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.OWNER.value
    )
    entry_id = await _seed_billing_prereqs(tenant_a.agency_id, tenant_a.brand_id, owner_id)
    headers = agency_headers(owner_token, tenant_a.agency_id)

    billable_resp = await client.get(
        "/api/v1/finance/billable-time",
        params={"brand_id": str(tenant_a.brand_id)},
        headers=headers,
    )
    assert billable_resp.status_code == 200
    assert len(billable_resp.json()) == 1

    draft_resp = await client.post(
        "/api/v1/finance/invoices/draft",
        json=_draft_payload(tenant_a.brand_id, entry_id),
        headers=headers,
    )
    assert draft_resp.status_code == 201
    invoice_id = draft_resp.json()["id"]
    assert draft_resp.json()["status"] == "draft"

    approve_resp = await client.post(
        f"/api/v1/finance/invoices/{invoice_id}/approve", headers=headers
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    send_resp = await client.post(f"/api/v1/finance/invoices/{invoice_id}/send", headers=headers)
    assert send_resp.status_code == 200
    assert send_resp.json()["status"] == "sent"

    pdf_resp = await client.get(f"/api/v1/finance/invoices/{invoice_id}/pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"

    csv_resp = await client.get(f"/api/v1/finance/invoices/{invoice_id}/csv", headers=headers)
    assert csv_resp.status_code == 200

    void_resp = await client.post(f"/api/v1/finance/invoices/{invoice_id}/void", headers=headers)
    assert void_resp.status_code == 200
    assert void_resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_admin_can_manage_invoices(client, tenants) -> None:
    tenant_a, _ = tenants
    admin_id, admin_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.ADMIN.value
    )
    entry_id = await _seed_billing_prereqs(tenant_a.agency_id, tenant_a.brand_id, admin_id)
    headers = agency_headers(admin_token, tenant_a.agency_id)

    draft_resp = await client.post(
        "/api/v1/finance/invoices/draft",
        json=_draft_payload(tenant_a.brand_id, entry_id),
        headers=headers,
    )
    assert draft_resp.status_code == 201

    invoice_id = draft_resp.json()["id"]
    approve_resp = await client.post(
        f"/api/v1/finance/invoices/{invoice_id}/approve", headers=headers
    )
    assert approve_resp.status_code == 200


# ------------------------------------------------------------------
# Brand Manager: view-only


@pytest.mark.asyncio
async def test_brand_manager_can_view_but_not_create_approve_or_void_invoices(
    client, tenants
) -> None:
    tenant_a, _ = tenants
    owner_id, owner_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.OWNER.value
    )
    entry_id = await _seed_billing_prereqs(tenant_a.agency_id, tenant_a.brand_id, owner_id)
    owner_headers = agency_headers(owner_token, tenant_a.agency_id)
    draft_resp = await client.post(
        "/api/v1/finance/invoices/draft",
        json=_draft_payload(tenant_a.brand_id, entry_id),
        headers=owner_headers,
    )
    invoice_id = draft_resp.json()["id"]

    _, bm_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.BRAND_MANAGER.value)
    bm_headers = agency_headers(bm_token, tenant_a.agency_id)

    billable_resp = await client.get(
        "/api/v1/finance/billable-time",
        params={"brand_id": str(tenant_a.brand_id)},
        headers=bm_headers,
    )
    assert billable_resp.status_code == 200

    list_resp = await client.get("/api/v1/finance/invoices", headers=bm_headers)
    assert list_resp.status_code == 200

    get_resp = await client.get(f"/api/v1/finance/invoices/{invoice_id}", headers=bm_headers)
    assert get_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/finance/invoices/draft",
        json=_draft_payload(tenant_a.brand_id, entry_id),
        headers=bm_headers,
    )
    assert create_resp.status_code == 403

    approve_resp = await client.post(
        f"/api/v1/finance/invoices/{invoice_id}/approve", headers=bm_headers
    )
    assert approve_resp.status_code == 403

    void_resp = await client.post(f"/api/v1/finance/invoices/{invoice_id}/void", headers=bm_headers)
    assert void_resp.status_code == 403


# ------------------------------------------------------------------
# Designer / Developer / Social Media Manager / Viewer: none of the five


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role",
    [
        AgencyMemberRole.DESIGNER.value,
        AgencyMemberRole.DEVELOPER.value,
        AgencyMemberRole.SOCIAL_MEDIA_MANAGER.value,
        AgencyMemberRole.VIEWER.value,
    ],
)
async def test_non_finance_roles_cannot_view_or_manage_invoices(client, tenants, role) -> None:
    tenant_a, _ = tenants
    _, token = await _add_agency_member(tenant_a.agency_id, role)
    headers = agency_headers(token, tenant_a.agency_id)

    billable_resp = await client.get(
        "/api/v1/finance/billable-time",
        params={"brand_id": str(tenant_a.brand_id)},
        headers=headers,
    )
    list_resp = await client.get("/api/v1/finance/invoices", headers=headers)
    create_resp = await client.post(
        "/api/v1/finance/invoices/draft",
        json={"brand_id": str(tenant_a.brand_id), "time_entry_ids": []},
        headers=headers,
    )
    assert billable_resp.status_code == 403
    assert list_resp.status_code == 403
    assert create_resp.status_code == 403


# ------------------------------------------------------------------
# Brand-portal JWTs must never reach agency-side finance endpoints


@pytest.mark.asyncio
async def test_brand_portal_user_jwt_cannot_reach_invoice_endpoints(client, tenants) -> None:
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/finance/invoices",
        headers={
            **brand_headers(tenant_a.brand_manager_token),
            "X-Agency-ID": str(tenant_a.agency_id),
        },
    )
    assert resp.status_code == 403


# ------------------------------------------------------------------
# Tenant isolation / IDOR


@pytest.mark.asyncio
async def test_agency_b_cannot_see_or_fetch_agency_a_invoices(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    owner_id, owner_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.OWNER.value
    )
    entry_id = await _seed_billing_prereqs(tenant_a.agency_id, tenant_a.brand_id, owner_id)
    draft_resp = await client.post(
        "/api/v1/finance/invoices/draft",
        json=_draft_payload(tenant_a.brand_id, entry_id),
        headers=agency_headers(owner_token, tenant_a.agency_id),
    )
    invoice_id = draft_resp.json()["id"]

    _, owner_b_token = await _add_agency_member(tenant_b.agency_id, AgencyMemberRole.OWNER.value)
    b_headers = agency_headers(owner_b_token, tenant_b.agency_id)

    list_resp = await client.get("/api/v1/finance/invoices", headers=b_headers)
    assert list_resp.status_code == 200
    assert list_resp.json() == []

    get_resp = await client.get(f"/api/v1/finance/invoices/{invoice_id}", headers=b_headers)
    assert get_resp.status_code == 404

    billable_resp = await client.get(
        "/api/v1/finance/billable-time",
        params={"brand_id": str(tenant_a.brand_id)},
        headers=b_headers,
    )
    assert billable_resp.status_code == 200
    assert billable_resp.json() == []

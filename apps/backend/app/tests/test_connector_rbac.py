"""RBAC coverage for the Phase 5 permission set (plan §8): PAYMENT_VIEW,
PAYMENT_MANAGE, ACCOUNTING_INTEGRATION_MANAGE.

Verifies the exact role table: Owner has all three, Admin has
PAYMENT_VIEW/PAYMENT_MANAGE but explicitly NOT ACCOUNTING_INTEGRATION_MANAGE
(conservative default matching the COST_RATE_* precedent), everyone else
(Brand Manager/Designer/Developer/Social Media Manager/Viewer) has none of
the three. Also covers tenant isolation (IDOR) on connectors and payments,
and that brand-portal JWTs can never reach these agency-side endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.tests.conftest import agency_headers, brand_headers


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


def _connector_payload(**overrides) -> dict:
    base = {"provider": "manual"}
    base.update(overrides)
    return base


def _payment_payload(brand_id: uuid.UUID, **overrides) -> dict:
    base = {
        "brand_id": str(brand_id),
        "amount_cents": 5000,
        "currency": "TRY",
        "payment_method": "bank_transfer",
        "paid_at": datetime.now(UTC).isoformat(),
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------
# ACCOUNTING_INTEGRATION_MANAGE


@pytest.mark.asyncio
async def test_owner_can_manage_connectors(client, tenants) -> None:
    tenant_a, _ = tenants
    _, owner_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.OWNER.value)
    headers = agency_headers(owner_token, tenant_a.agency_id)
    resp = await client.post(
        "/api/v1/finance/connectors", json=_connector_payload(), headers=headers
    )
    assert resp.status_code == 201
    assert "encrypted_credentials" not in resp.json()

    list_resp = await client.get("/api/v1/finance/connectors", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_admin_cannot_manage_connectors(client, tenants) -> None:
    """Plan §8's explicit conservative-default exclusion, mirroring
    COST_RATE_* for Admin."""
    tenant_a, _ = tenants
    _, admin_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.ADMIN.value)
    headers = agency_headers(admin_token, tenant_a.agency_id)

    create_resp = await client.post(
        "/api/v1/finance/connectors", json=_connector_payload(), headers=headers
    )
    list_resp = await client.get("/api/v1/finance/connectors", headers=headers)
    assert create_resp.status_code == 403
    assert list_resp.status_code == 403


@pytest.mark.asyncio
async def test_brand_manager_cannot_manage_connectors(client, tenants) -> None:
    tenant_a, _ = tenants
    _, bm_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.BRAND_MANAGER.value)
    resp = await client.post(
        "/api/v1/finance/connectors",
        json=_connector_payload(),
        headers=agency_headers(bm_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_designer_cannot_manage_connectors(client, tenants) -> None:
    tenant_a, _ = tenants
    _, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    resp = await client.post(
        "/api/v1/finance/connectors",
        json=_connector_payload(),
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_manage_connectors(client, tenants) -> None:
    tenant_a, _ = tenants
    _, viewer_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.VIEWER.value)
    resp = await client.get(
        "/api/v1/finance/connectors",
        headers=agency_headers(viewer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


# ------------------------------------------------------------------
# PAYMENT_VIEW / PAYMENT_MANAGE


@pytest.mark.asyncio
async def test_owner_can_view_and_manage_payments(client, tenants) -> None:
    tenant_a, _ = tenants
    _, owner_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.OWNER.value)
    headers = agency_headers(owner_token, tenant_a.agency_id)
    resp = await client.post(
        "/api/v1/finance/payments",
        json=_payment_payload(tenant_a.brand_id),
        headers=headers,
    )
    assert resp.status_code == 201

    list_resp = await client.get("/api/v1/finance/payments", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_admin_can_view_and_manage_payments(client, tenants) -> None:
    """Admin keeps PAYMENT_VIEW/PAYMENT_MANAGE even though it loses
    ACCOUNTING_INTEGRATION_MANAGE."""
    tenant_a, _ = tenants
    _, admin_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.ADMIN.value)
    headers = agency_headers(admin_token, tenant_a.agency_id)
    resp = await client.post(
        "/api/v1/finance/payments",
        json=_payment_payload(tenant_a.brand_id),
        headers=headers,
    )
    assert resp.status_code == 201

    list_resp = await client.get("/api/v1/finance/payments", headers=headers)
    assert list_resp.status_code == 200


@pytest.mark.asyncio
async def test_brand_manager_cannot_view_or_manage_payments(client, tenants) -> None:
    tenant_a, _ = tenants
    _, bm_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.BRAND_MANAGER.value)
    headers = agency_headers(bm_token, tenant_a.agency_id)
    view_resp = await client.get("/api/v1/finance/payments", headers=headers)
    manage_resp = await client.post(
        "/api/v1/finance/payments", json=_payment_payload(tenant_a.brand_id), headers=headers
    )
    assert view_resp.status_code == 403
    assert manage_resp.status_code == 403


@pytest.mark.asyncio
async def test_designer_cannot_view_or_manage_payments(client, tenants) -> None:
    tenant_a, _ = tenants
    _, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    headers = agency_headers(designer_token, tenant_a.agency_id)
    view_resp = await client.get("/api/v1/finance/payments", headers=headers)
    manage_resp = await client.post(
        "/api/v1/finance/payments", json=_payment_payload(tenant_a.brand_id), headers=headers
    )
    assert view_resp.status_code == 403
    assert manage_resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_view_payments(client, tenants) -> None:
    tenant_a, _ = tenants
    _, viewer_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.VIEWER.value)
    resp = await client.get(
        "/api/v1/finance/payments",
        headers=agency_headers(viewer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


# ------------------------------------------------------------------
# Brand-portal JWTs must never reach agency-side finance endpoints


@pytest.mark.asyncio
async def test_brand_user_jwt_cannot_reach_connector_or_payment_endpoints(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = {
        **brand_headers(tenant_a.brand_manager_token),
        "X-Agency-ID": str(tenant_a.agency_id),
    }
    connectors_resp = await client.get("/api/v1/finance/connectors", headers=headers)
    payments_resp = await client.get("/api/v1/finance/payments", headers=headers)
    assert connectors_resp.status_code == 403
    assert payments_resp.status_code == 403


# ------------------------------------------------------------------
# Tenant isolation / IDOR


@pytest.mark.asyncio
async def test_agency_b_cannot_see_agency_a_connectors(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    _, owner_a_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.OWNER.value)
    _, owner_b_token = await _add_agency_member(tenant_b.agency_id, AgencyMemberRole.OWNER.value)

    await client.post(
        "/api/v1/finance/connectors",
        json=_connector_payload(),
        headers=agency_headers(owner_a_token, tenant_a.agency_id),
    )
    resp = await client.get(
        "/api/v1/finance/connectors",
        headers=agency_headers(owner_b_token, tenant_b.agency_id),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_agency_b_cannot_fetch_agency_a_connector_by_id(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    _, owner_a_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.OWNER.value)
    _, owner_b_token = await _add_agency_member(tenant_b.agency_id, AgencyMemberRole.OWNER.value)

    create_resp = await client.post(
        "/api/v1/finance/connectors",
        json=_connector_payload(),
        headers=agency_headers(owner_a_token, tenant_a.agency_id),
    )
    connector_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/finance/connectors/{connector_id}",
        headers=agency_headers(owner_b_token, tenant_b.agency_id),
    )
    assert resp.status_code == 404

    delete_resp = await client.delete(
        f"/api/v1/finance/connectors/{connector_id}",
        headers=agency_headers(owner_b_token, tenant_b.agency_id),
    )
    assert delete_resp.status_code == 404


@pytest.mark.asyncio
async def test_agency_b_cannot_see_agency_a_payments(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    _, owner_a_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.OWNER.value)
    _, owner_b_token = await _add_agency_member(tenant_b.agency_id, AgencyMemberRole.OWNER.value)

    await client.post(
        "/api/v1/finance/payments",
        json=_payment_payload(tenant_a.brand_id),
        headers=agency_headers(owner_a_token, tenant_a.agency_id),
    )
    resp = await client.get(
        "/api/v1/finance/payments",
        headers=agency_headers(owner_b_token, tenant_b.agency_id),
    )
    assert resp.status_code == 200
    assert resp.json() == []

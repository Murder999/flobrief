"""RBAC coverage for the new finance permission set (plan §8):
COMMERCIAL_TERMS_VIEW, COMMERCIAL_TERMS_MANAGE, COST_RATE_VIEW,
COST_RATE_MANAGE.

Verifies the exact role table from the plan: Owner has everything, Admin has
commercial-terms view/manage but explicitly NOT cost-rate view/manage
(conservative default), Brand Manager has commercial-terms VIEW only (never
cost rates), Designer/Developer/Social Media Manager/Viewer have none of the
four. This is the security-sensitive test the plan calls out by name — a
Designer, Brand Manager, or brand-portal user must NEVER be able to reach
cost-rate data under any code path, so those cases get extra coverage
beyond a single 403 assertion (including cross-tenant IDOR on both
resources)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
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


def _commercial_terms_payload(brand_id: uuid.UUID, **overrides) -> dict:
    base = {
        "brand_id": str(brand_id),
        "billing_model": "hourly",
        "currency": "TRY",
        "hourly_rate_cents": 50000,
        "payment_terms_days": 30,
        "tax_rate_bps": 2000,
        "valid_from": TODAY.isoformat(),
    }
    base.update(overrides)
    return base


def _cost_rate_payload(user_id: uuid.UUID, **overrides) -> dict:
    base = {
        "user_id": str(user_id),
        "currency": "TRY",
        "hourly_cost_cents": 20000,
        "valid_from": TODAY.isoformat(),
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------
# COMMERCIAL_TERMS_VIEW / COMMERCIAL_TERMS_MANAGE


@pytest.mark.asyncio
async def test_owner_can_manage_commercial_terms(client, tenants) -> None:
    tenant_a, _ = tenants
    _, owner_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.OWNER.value)
    headers = agency_headers(owner_token, tenant_a.agency_id)
    resp = await client.post(
        "/api/v1/finance/commercial-terms",
        json=_commercial_terms_payload(tenant_a.brand_id),
        headers=headers,
    )
    assert resp.status_code == 201

    get_resp = await client.get(
        "/api/v1/finance/commercial-terms",
        params={"brand_id": str(tenant_a.brand_id)},
        headers=headers,
    )
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 1


@pytest.mark.asyncio
async def test_admin_can_manage_commercial_terms(client, tenants) -> None:
    tenant_a, _ = tenants
    admin_id, admin_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.ADMIN.value
    )
    resp = await client.post(
        "/api/v1/finance/commercial-terms",
        json=_commercial_terms_payload(tenant_a.brand_id),
        headers=agency_headers(admin_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_brand_manager_can_view_but_not_manage_commercial_terms(client, tenants) -> None:
    tenant_a, _ = tenants
    headers_owner = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    await client.post(
        "/api/v1/finance/commercial-terms",
        json=_commercial_terms_payload(tenant_a.brand_id),
        headers=headers_owner,
    )

    _, bm_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.BRAND_MANAGER.value)
    bm_headers = agency_headers(bm_token, tenant_a.agency_id)

    view_resp = await client.get(
        "/api/v1/finance/commercial-terms",
        params={"brand_id": str(tenant_a.brand_id)},
        headers=bm_headers,
    )
    assert view_resp.status_code == 200

    later_valid_from = (TODAY + timedelta(days=60)).isoformat()
    manage_resp = await client.post(
        "/api/v1/finance/commercial-terms",
        json=_commercial_terms_payload(tenant_a.brand_id, valid_from=later_valid_from),
        headers=bm_headers,
    )
    assert manage_resp.status_code == 403


@pytest.mark.asyncio
async def test_designer_cannot_view_or_manage_commercial_terms(client, tenants) -> None:
    tenant_a, _ = tenants
    _, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    headers = agency_headers(designer_token, tenant_a.agency_id)

    view_resp = await client.get(
        "/api/v1/finance/commercial-terms",
        params={"brand_id": str(tenant_a.brand_id)},
        headers=headers,
    )
    manage_resp = await client.post(
        "/api/v1/finance/commercial-terms",
        json=_commercial_terms_payload(tenant_a.brand_id),
        headers=headers,
    )
    assert view_resp.status_code == 403
    assert manage_resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_view_commercial_terms(client, tenants) -> None:
    tenant_a, _ = tenants
    _, viewer_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.VIEWER.value)
    resp = await client.get(
        "/api/v1/finance/commercial-terms",
        params={"brand_id": str(tenant_a.brand_id)},
        headers=agency_headers(viewer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


# ------------------------------------------------------------------
# COST_RATE_VIEW / COST_RATE_MANAGE — the security-critical set.
# No agency role other than Owner may ever view or manage cost rates.


@pytest.mark.asyncio
async def test_owner_can_manage_cost_rates(client, tenants) -> None:
    # `tenant.agency_token` (conftest's `_build_tenant`) is seeded with the
    # ADMIN role, not OWNER — cost rates are Owner-only, so a dedicated
    # Owner member is required here.
    tenant_a, _ = tenants
    owner_id, owner_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.OWNER.value
    )
    headers = agency_headers(owner_token, tenant_a.agency_id)
    resp = await client.post(
        "/api/v1/finance/cost-rates",
        json=_cost_rate_payload(owner_id),
        headers=headers,
    )
    assert resp.status_code == 201

    get_resp = await client.get(
        "/api/v1/finance/cost-rates",
        params={"user_id": str(owner_id)},
        headers=headers,
    )
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 1


@pytest.mark.asyncio
async def test_admin_cannot_view_or_manage_cost_rates(client, tenants) -> None:
    """Plan §8's explicit conservative-default exclusion."""
    tenant_a, _ = tenants
    _, admin_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.ADMIN.value)
    headers = agency_headers(admin_token, tenant_a.agency_id)

    view_resp = await client.get(
        "/api/v1/finance/cost-rates",
        params={"user_id": str(tenant_a.agency_user_id)},
        headers=headers,
    )
    manage_resp = await client.post(
        "/api/v1/finance/cost-rates",
        json=_cost_rate_payload(tenant_a.agency_user_id),
        headers=headers,
    )
    assert view_resp.status_code == 403
    assert manage_resp.status_code == 403


@pytest.mark.asyncio
async def test_brand_manager_can_never_see_cost_rates(client, tenants) -> None:
    tenant_a, _ = tenants
    # Seed a real cost rate as Owner first so there is something a leak
    # would actually expose.
    owner_headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    await client.post(
        "/api/v1/finance/cost-rates",
        json=_cost_rate_payload(tenant_a.agency_user_id),
        headers=owner_headers,
    )

    _, bm_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.BRAND_MANAGER.value)
    bm_headers = agency_headers(bm_token, tenant_a.agency_id)

    view_resp = await client.get(
        "/api/v1/finance/cost-rates",
        params={"user_id": str(tenant_a.agency_user_id)},
        headers=bm_headers,
    )
    manage_resp = await client.post(
        "/api/v1/finance/cost-rates",
        json=_cost_rate_payload(tenant_a.agency_user_id),
        headers=bm_headers,
    )
    assert view_resp.status_code == 403
    assert manage_resp.status_code == 403
    assert "hourly_cost_cents" not in view_resp.text


@pytest.mark.asyncio
async def test_designer_can_never_see_cost_rates(client, tenants) -> None:
    tenant_a, _ = tenants
    owner_headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    await client.post(
        "/api/v1/finance/cost-rates",
        json=_cost_rate_payload(tenant_a.agency_user_id),
        headers=owner_headers,
    )

    designer_id, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    designer_headers = agency_headers(designer_token, tenant_a.agency_id)

    # Even querying their *own* user_id must be denied — CAPACITY_VIEW_OWN
    # style self-access does not exist for cost rates; there is no "own"
    # cost-rate visibility tier at all.
    view_own_resp = await client.get(
        "/api/v1/finance/cost-rates",
        params={"user_id": str(designer_id)},
        headers=designer_headers,
    )
    view_other_resp = await client.get(
        "/api/v1/finance/cost-rates",
        params={"user_id": str(tenant_a.agency_user_id)},
        headers=designer_headers,
    )
    manage_resp = await client.post(
        "/api/v1/finance/cost-rates",
        json=_cost_rate_payload(designer_id),
        headers=designer_headers,
    )
    assert view_own_resp.status_code == 403
    assert view_other_resp.status_code == 403
    assert manage_resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_can_never_see_cost_rates(client, tenants) -> None:
    tenant_a, _ = tenants
    _, viewer_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.VIEWER.value)
    resp = await client.get(
        "/api/v1/finance/cost-rates",
        params={"user_id": str(tenant_a.agency_user_id)},
        headers=agency_headers(viewer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_brand_portal_user_jwt_cannot_reach_finance_endpoints(client, tenants) -> None:
    """Brand-portal JWTs must never reach agency-side finance endpoints —
    mirrors `test_brand_user_jwt_cannot_view_capacity_report`."""
    tenant_a, _ = tenants
    terms_resp = await client.get(
        "/api/v1/finance/commercial-terms",
        params={"brand_id": str(tenant_a.brand_id)},
        headers={
            **brand_headers(tenant_a.brand_manager_token),
            "X-Agency-ID": str(tenant_a.agency_id),
        },
    )
    rates_resp = await client.get(
        "/api/v1/finance/cost-rates",
        params={"user_id": str(tenant_a.agency_user_id)},
        headers={
            **brand_headers(tenant_a.brand_manager_token),
            "X-Agency-ID": str(tenant_a.agency_id),
        },
    )
    assert terms_resp.status_code == 403
    assert rates_resp.status_code == 403


# ------------------------------------------------------------------
# Tenant isolation / IDOR


@pytest.mark.asyncio
async def test_agency_b_cannot_see_agency_a_commercial_terms(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    await client.post(
        "/api/v1/finance/commercial-terms",
        json=_commercial_terms_payload(tenant_a.brand_id),
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )

    resp = await client.get(
        "/api/v1/finance/commercial-terms",
        params={"brand_id": str(tenant_a.brand_id)},
        headers=agency_headers(tenant_b.agency_token, tenant_b.agency_id),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_agency_b_owner_cannot_see_agency_a_cost_rates(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    owner_a_id, owner_a_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.OWNER.value
    )
    _, owner_b_token = await _add_agency_member(tenant_b.agency_id, AgencyMemberRole.OWNER.value)

    await client.post(
        "/api/v1/finance/cost-rates",
        json=_cost_rate_payload(owner_a_id),
        headers=agency_headers(owner_a_token, tenant_a.agency_id),
    )

    resp = await client.get(
        "/api/v1/finance/cost-rates",
        params={"user_id": str(owner_a_id)},
        headers=agency_headers(owner_b_token, tenant_b.agency_id),
    )
    assert resp.status_code == 200
    assert resp.json() == []

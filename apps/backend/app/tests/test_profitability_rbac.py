"""RBAC coverage for `PROFITABILITY_VIEW` (plan §8, Phase 6):
`/finance/profitability/overview|brand/{id}|brief/{id}`.

Verifies the plan's exact role table — Owner and Admin see full profitability
including cost/margin; Brand Manager has `PROFITABILITY_VIEW` but NOT
`COST_RATE_VIEW`, so it must see revenue/WIP figures with cost/margin fields
explicitly nulled (never a fabricated zero) — this is the security-critical
scenario the plan calls out by name; Designer/Developer/Social Media
Manager/Viewer have no access at all; brand-portal JWTs cannot reach any
agency-side finance endpoint; and cross-tenant IDOR is blocked on both the
brand and brief detail endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency_member import AgencyMember
from app.models.commercial_terms import CommercialTerms, MemberCostRate
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
    """Active hourly `CommercialTerms` + a `MemberCostRate` for the acting
    user + one locked, billable `TimeEntry` — the minimum fixture for a
    revenue-and-cost-bearing profitability figure once invoiced."""
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
        session.add(
            MemberCostRate(
                id=uuid.uuid4(),
                agency_id=agency_id,
                user_id=user_id,
                currency="TRY",
                hourly_cost_cents=20_000,
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


async def _invoice_and_approve(client, headers, brand_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    draft_resp = await client.post(
        "/api/v1/finance/invoices/draft",
        json={"brand_id": str(brand_id), "time_entry_ids": [str(entry_id)]},
        headers=headers,
    )
    assert draft_resp.status_code == 201, draft_resp.text
    invoice_id = draft_resp.json()["id"]
    approve_resp = await client.post(
        f"/api/v1/finance/invoices/{invoice_id}/approve", headers=headers
    )
    assert approve_resp.status_code == 200, approve_resp.text


# ------------------------------------------------------------------
# Owner / Admin: full visibility including cost and margin


@pytest.mark.asyncio
async def test_owner_sees_full_profitability_including_cost_and_margin(client, tenants) -> None:
    tenant_a, _ = tenants
    owner_id, owner_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.OWNER.value
    )
    entry_id = await _seed_billing_prereqs(tenant_a.agency_id, tenant_a.brand_id, owner_id)
    headers = agency_headers(owner_token, tenant_a.agency_id)
    await _invoice_and_approve(client, headers, tenant_a.brand_id, entry_id)

    overview_resp = await client.get("/api/v1/finance/profitability/overview", headers=headers)
    assert overview_resp.status_code == 200
    currencies = overview_resp.json()["currencies"]
    try_currency = next(c for c in currencies if c["currency"] == "TRY")
    assert try_currency["invoiced_revenue_cents"] == 120_000  # 2h*50000, +20% tax
    assert try_currency["internal_cost_cents"] == 40_000  # 2h*20000
    assert try_currency["cost_data_visible"] is True
    assert try_currency["average_margin_pct"] is not None

    brand_resp = await client.get(
        f"/api/v1/finance/profitability/brand/{tenant_a.brand_id}", headers=headers
    )
    assert brand_resp.status_code == 200
    brand_currency = next(c for c in brand_resp.json()["currencies"] if c["currency"] == "TRY")
    assert brand_currency["internal_cost_cents"] == 40_000
    assert brand_currency["gross_margin_pct"] is not None

    brief_resp = await client.get(
        f"/api/v1/finance/profitability/brief/{tenant_a.brief_id}", headers=headers
    )
    assert brief_resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_sees_profitability_but_not_cost_or_margin(client, tenants) -> None:
    """Admin has `PROFITABILITY_VIEW` but — per plan §8's conservative
    default, already established for cost rates by
    `test_finance_rbac.py::test_admin_cannot_view_or_manage_cost_rates` — is
    explicitly excluded from `COST_RATE_VIEW`. Profitability must honor that
    exact same gate: Admin sees revenue, never cost/margin."""
    tenant_a, _ = tenants
    admin_id, admin_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.ADMIN.value
    )
    entry_id = await _seed_billing_prereqs(tenant_a.agency_id, tenant_a.brand_id, admin_id)
    headers = agency_headers(admin_token, tenant_a.agency_id)
    await _invoice_and_approve(client, headers, tenant_a.brand_id, entry_id)

    overview_resp = await client.get("/api/v1/finance/profitability/overview", headers=headers)
    assert overview_resp.status_code == 200
    try_currency = next(c for c in overview_resp.json()["currencies"] if c["currency"] == "TRY")
    assert try_currency["invoiced_revenue_cents"] == 120_000
    assert try_currency["internal_cost_cents"] is None
    assert try_currency["gross_profit_cents"] is None
    assert try_currency["average_margin_pct"] is None
    assert try_currency["cost_data_visible"] is False


# ------------------------------------------------------------------
# Brand Manager: PROFITABILITY_VIEW without COST_RATE_VIEW — the
# security-critical scenario the plan calls out by name.


@pytest.mark.asyncio
async def test_brand_manager_sees_revenue_but_never_cost_or_margin(client, tenants) -> None:
    tenant_a, _ = tenants
    owner_id, owner_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.OWNER.value
    )
    entry_id = await _seed_billing_prereqs(tenant_a.agency_id, tenant_a.brand_id, owner_id)
    owner_headers = agency_headers(owner_token, tenant_a.agency_id)
    await _invoice_and_approve(client, owner_headers, tenant_a.brand_id, entry_id)

    _, bm_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.BRAND_MANAGER.value)
    bm_headers = agency_headers(bm_token, tenant_a.agency_id)

    overview_resp = await client.get("/api/v1/finance/profitability/overview", headers=bm_headers)
    assert overview_resp.status_code == 200
    overview_json = overview_resp.json()
    try_currency = next(c for c in overview_json["currencies"] if c["currency"] == "TRY")
    assert try_currency["invoiced_revenue_cents"] == 120_000  # revenue still visible
    assert try_currency["internal_cost_cents"] is None  # never a fabricated 0
    assert try_currency["gross_profit_cents"] is None
    assert try_currency["average_margin_pct"] is None
    assert try_currency["cost_data_visible"] is False
    # Margin-derived risk-flag types must not leak either — their message
    # text would otherwise carry a margin percentage.
    risk_types = {f["type"] for f in overview_json["risk_flags"]}
    assert "dusuk_kar_marji" not in risk_types
    assert "negatif_kar_marji" not in risk_types

    brand_resp = await client.get(
        f"/api/v1/finance/profitability/brand/{tenant_a.brand_id}", headers=bm_headers
    )
    assert brand_resp.status_code == 200
    brand_json = brand_resp.json()
    brand_currency = next(c for c in brand_json["currencies"] if c["currency"] == "TRY")
    assert brand_currency["invoiced_revenue_cents"] == 120_000
    assert brand_currency["internal_cost_cents"] is None
    assert brand_currency["gross_profit_cents"] is None
    assert brand_currency["gross_margin_pct"] is None
    assert brand_currency["cost_data_visible"] is False

    brief_resp = await client.get(
        f"/api/v1/finance/profitability/brief/{tenant_a.brief_id}", headers=bm_headers
    )
    assert brief_resp.status_code == 200


# ------------------------------------------------------------------
# Designer / Developer / Social Media Manager / Viewer: no access at all


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
async def test_non_finance_roles_cannot_view_profitability(client, tenants, role) -> None:
    tenant_a, _ = tenants
    _, token = await _add_agency_member(tenant_a.agency_id, role)
    headers = agency_headers(token, tenant_a.agency_id)

    overview_resp = await client.get("/api/v1/finance/profitability/overview", headers=headers)
    brand_resp = await client.get(
        f"/api/v1/finance/profitability/brand/{tenant_a.brand_id}", headers=headers
    )
    brief_resp = await client.get(
        f"/api/v1/finance/profitability/brief/{tenant_a.brief_id}", headers=headers
    )
    assert overview_resp.status_code == 403
    assert brand_resp.status_code == 403
    assert brief_resp.status_code == 403


# ------------------------------------------------------------------
# Brand-portal JWTs must never reach agency-side finance endpoints


@pytest.mark.asyncio
async def test_brand_portal_user_jwt_cannot_reach_profitability_endpoints(client, tenants) -> None:
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/finance/profitability/overview",
        headers={
            **brand_headers(tenant_a.brand_manager_token),
            "X-Agency-ID": str(tenant_a.agency_id),
        },
    )
    assert resp.status_code == 403


# ------------------------------------------------------------------
# Tenant isolation / IDOR


@pytest.mark.asyncio
async def test_agency_b_cannot_see_agency_a_profitability(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    owner_id, owner_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.OWNER.value
    )
    entry_id = await _seed_billing_prereqs(tenant_a.agency_id, tenant_a.brand_id, owner_id)
    owner_headers = agency_headers(owner_token, tenant_a.agency_id)
    await _invoice_and_approve(client, owner_headers, tenant_a.brand_id, entry_id)

    _, owner_b_token = await _add_agency_member(tenant_b.agency_id, AgencyMemberRole.OWNER.value)
    b_headers = agency_headers(owner_b_token, tenant_b.agency_id)

    brand_resp = await client.get(
        f"/api/v1/finance/profitability/brand/{tenant_a.brand_id}", headers=b_headers
    )
    assert brand_resp.status_code == 404

    brief_resp = await client.get(
        f"/api/v1/finance/profitability/brief/{tenant_a.brief_id}", headers=b_headers
    )
    assert brief_resp.status_code == 404

    # Agency B's own overview must reflect only agency B's (empty) data —
    # agency A's revenue must never leak into it.
    overview_resp = await client.get("/api/v1/finance/profitability/overview", headers=b_headers)
    assert overview_resp.status_code == 200
    for c in overview_resp.json()["currencies"]:
        assert c["invoiced_revenue_cents"] == 0

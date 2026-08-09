"""RBAC coverage for the new capacity permission set (plan §8):
CAPACITY_VIEW_OWN, CAPACITY_VIEW_TEAM, CAPACITY_MANAGE_SCHEDULE,
CAPACITY_MANAGE_ALLOCATION, TIME_OFF_REQUEST, TIME_OFF_APPROVE.

Verifies the exact role table from the plan: Owner/Admin have everything,
Brand Manager has CAPACITY_VIEW_TEAM only (no manage-schedule/allocation, no
time-off approve), Designer/Developer/Social Media Manager have
CAPACITY_VIEW_OWN + TIME_OFF_REQUEST only, Viewer has CAPACITY_VIEW_OWN only.
Also covers tenant isolation (IDOR) on allocations."""

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
TOMORROW = TODAY + timedelta(days=1)

_FULL_WEEK_DAYS = [
    {"weekday": d, "is_working_day": d < 5, "capacity_minutes": 480 if d < 5 else 0}
    for d in range(7)
]


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


def _schedule_payload(user_id: uuid.UUID) -> dict:
    return {"user_id": str(user_id), "timezone": "Europe/Istanbul", "days": _FULL_WEEK_DAYS}


def _allocation_payload(user_id: uuid.UUID) -> dict:
    return {
        "user_id": str(user_id),
        "start_date": TODAY.isoformat(),
        "end_date": TOMORROW.isoformat(),
        "allocated_minutes": 60,
    }


# ------------------------------------------------------------------
# CAPACITY_MANAGE_SCHEDULE


@pytest.mark.asyncio
async def test_admin_can_manage_schedule(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    resp = await client.put(
        f"/api/v1/capacity/schedules/{tenant_a.agency_user_id}",
        json=_schedule_payload(tenant_a.agency_user_id),
        headers=headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_designer_cannot_manage_schedule(client, tenants) -> None:
    tenant_a, _ = tenants
    designer_id, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    resp = await client.put(
        f"/api/v1/capacity/schedules/{designer_id}",
        json=_schedule_payload(designer_id),
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_brand_manager_cannot_manage_schedule(client, tenants) -> None:
    tenant_a, _ = tenants
    bm_id, bm_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.BRAND_MANAGER.value
    )
    resp = await client.put(
        f"/api/v1/capacity/schedules/{bm_id}",
        json=_schedule_payload(bm_id),
        headers=agency_headers(bm_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


# ------------------------------------------------------------------
# CAPACITY_VIEW_OWN / CAPACITY_VIEW_TEAM


@pytest.mark.asyncio
async def test_designer_can_view_own_capacity_report(client, tenants) -> None:
    tenant_a, _ = tenants
    designer_id, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    resp = await client.get(
        f"/api/v1/capacity/report/user/{designer_id}",
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_designer_cannot_view_teammate_capacity_report(client, tenants) -> None:
    tenant_a, _ = tenants
    designer_id, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    resp = await client.get(
        f"/api/v1/capacity/report/user/{tenant_a.agency_user_id}",
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_can_view_own_but_not_team_report(client, tenants) -> None:
    tenant_a, _ = tenants
    viewer_id, viewer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.VIEWER.value
    )
    own_resp = await client.get(
        f"/api/v1/capacity/report/user/{viewer_id}",
        headers=agency_headers(viewer_token, tenant_a.agency_id),
    )
    team_resp = await client.get(
        "/api/v1/capacity/report/team",
        headers=agency_headers(viewer_token, tenant_a.agency_id),
    )
    assert own_resp.status_code == 200
    assert team_resp.status_code == 403


@pytest.mark.asyncio
async def test_brand_manager_can_view_team_report(client, tenants) -> None:
    tenant_a, _ = tenants
    _, bm_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.BRAND_MANAGER.value)
    resp = await client.get(
        "/api/v1/capacity/report/team",
        headers=agency_headers(bm_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_brand_manager_can_view_brand_and_unassigned_reports(client, tenants) -> None:
    tenant_a, _ = tenants
    _, bm_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.BRAND_MANAGER.value)
    headers = agency_headers(bm_token, tenant_a.agency_id)
    brand_resp = await client.get(
        f"/api/v1/capacity/report/brand/{tenant_a.brand_id}", headers=headers
    )
    unassigned_resp = await client.get("/api/v1/capacity/report/unassigned", headers=headers)
    assert brand_resp.status_code == 200
    assert unassigned_resp.status_code == 200


# ------------------------------------------------------------------
# CAPACITY_MANAGE_ALLOCATION


@pytest.mark.asyncio
async def test_admin_can_manage_allocation(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    resp = await client.post(
        "/api/v1/capacity/allocations",
        json=_allocation_payload(tenant_a.agency_user_id),
        headers=headers,
    )
    assert resp.status_code == 201
    assert "allocation" in resp.json()


@pytest.mark.asyncio
async def test_brand_manager_cannot_manage_allocation(client, tenants) -> None:
    tenant_a, _ = tenants
    bm_id, bm_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.BRAND_MANAGER.value
    )
    resp = await client.post(
        "/api/v1/capacity/allocations",
        json=_allocation_payload(bm_id),
        headers=agency_headers(bm_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_designer_cannot_manage_allocation(client, tenants) -> None:
    tenant_a, _ = tenants
    designer_id, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    resp = await client.post(
        "/api/v1/capacity/allocations",
        json=_allocation_payload(designer_id),
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


# ------------------------------------------------------------------
# TIME_OFF_REQUEST / TIME_OFF_APPROVE


@pytest.mark.asyncio
async def test_designer_can_request_own_time_off(client, tenants) -> None:
    tenant_a, _ = tenants
    designer_id, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    resp = await client.post(
        "/api/v1/capacity/time-off",
        json={
            "user_id": str(designer_id),
            "start_at": f"{TODAY.isoformat()}T00:00:00Z",
            "end_at": f"{TODAY.isoformat()}T00:00:00Z",
            "all_day": True,
            "type": "vacation",
        },
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_designer_cannot_request_time_off_for_others(client, tenants) -> None:
    tenant_a, _ = tenants
    _, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    resp = await client.post(
        "/api/v1/capacity/time-off",
        json={
            "user_id": str(tenant_a.agency_user_id),
            "start_at": f"{TODAY.isoformat()}T00:00:00Z",
            "end_at": f"{TODAY.isoformat()}T00:00:00Z",
            "all_day": True,
            "type": "vacation",
        },
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_request_time_off(client, tenants) -> None:
    tenant_a, _ = tenants
    viewer_id, viewer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.VIEWER.value
    )
    resp = await client.post(
        "/api/v1/capacity/time-off",
        json={
            "user_id": str(viewer_id),
            "start_at": f"{TODAY.isoformat()}T00:00:00Z",
            "end_at": f"{TODAY.isoformat()}T00:00:00Z",
            "all_day": True,
            "type": "vacation",
        },
        headers=agency_headers(viewer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_designer_cannot_approve_time_off(client, tenants) -> None:
    tenant_a, _ = tenants
    designer_id, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    create_resp = await client.post(
        "/api/v1/capacity/time-off",
        json={
            "user_id": str(designer_id),
            "start_at": f"{TODAY.isoformat()}T00:00:00Z",
            "end_at": f"{TODAY.isoformat()}T00:00:00Z",
            "all_day": True,
            "type": "vacation",
        },
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    time_off_id = create_resp.json()["time_off"]["id"]

    resp = await client.patch(
        f"/api/v1/capacity/time-off/{time_off_id}/approve",
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_approve_time_off(client, tenants) -> None:
    tenant_a, _ = tenants
    designer_id, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    create_resp = await client.post(
        "/api/v1/capacity/time-off",
        json={
            "user_id": str(designer_id),
            "start_at": f"{TODAY.isoformat()}T00:00:00Z",
            "end_at": f"{TODAY.isoformat()}T00:00:00Z",
            "all_day": True,
            "type": "vacation",
        },
        headers=agency_headers(designer_token, tenant_a.agency_id),
    )
    time_off_id = create_resp.json()["time_off"]["id"]

    resp = await client.patch(
        f"/api/v1/capacity/time-off/{time_off_id}/approve",
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert resp.status_code == 200
    assert resp.json()["time_off"]["status"] == "approved"


# ------------------------------------------------------------------
# Brand-portal JWTs must never reach agency-side capacity endpoints


@pytest.mark.asyncio
async def test_brand_user_jwt_cannot_view_capacity_report(client, tenants) -> None:
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/capacity/report/team",
        headers={
            **brand_headers(tenant_a.brand_manager_token),
            "X-Agency-ID": str(tenant_a.agency_id),
        },
    )
    assert resp.status_code == 403


# ------------------------------------------------------------------
# Tenant isolation / IDOR on allocations


@pytest.mark.asyncio
async def test_agency_b_cannot_delete_agency_a_allocation(client, tenants) -> None:
    tenant_a, tenant_b = tenants
    create_resp = await client.post(
        "/api/v1/capacity/allocations",
        json=_allocation_payload(tenant_a.agency_user_id),
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    allocation_id = create_resp.json()["allocation"]["id"]

    delete_resp = await client.delete(
        f"/api/v1/capacity/allocations/{allocation_id}",
        headers=agency_headers(tenant_b.agency_token, tenant_b.agency_id),
    )
    assert delete_resp.status_code == 404

    # The allocation must still exist untouched under tenant A.
    list_resp = await client.get(
        "/api/v1/capacity/allocations",
        params={"user_id": str(tenant_a.agency_user_id)},
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )
    assert any(a["id"] == allocation_id for a in list_resp.json())


@pytest.mark.asyncio
async def test_agency_b_cannot_see_agency_a_users_schedule_as_own_schedule(client, tenants) -> None:
    """agency B admin querying agency A's user_id under agency B's tenant
    scope must see "no schedule" (structurally isolated by agency_id), never
    agency A's real schedule data."""
    tenant_a, tenant_b = tenants
    await client.put(
        f"/api/v1/capacity/schedules/{tenant_a.agency_user_id}",
        json=_schedule_payload(tenant_a.agency_user_id),
        headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
    )

    resp = await client.get(
        f"/api/v1/capacity/report/user/{tenant_a.agency_user_id}",
        headers=agency_headers(tenant_b.agency_token, tenant_b.agency_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["net_capacity_minutes"] == 0
    assert body["capacity_status_reason"] == "no_schedule"

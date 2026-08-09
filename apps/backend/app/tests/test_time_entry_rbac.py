"""RBAC tests for time tracking: own-entry edits need only membership, peer
edits need TIME_ENTRY_MANAGE, VIEWER cannot log time at all, and brand-portal
JWTs can't reach any agency-side time-tracking endpoint (there is no
brand-portal router for this module — a structural guarantee, not just a
permission check)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.tests.conftest import agency_headers, brand_headers

START_URL = "/api/v1/time-entries/start"
MANUAL_URL = "/api/v1/time-entries"


async def _add_agency_member(agency_id: uuid.UUID, role: str) -> tuple[uuid.UUID, str]:
    """Creates an additional user with the given role in an existing agency."""
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


@pytest.mark.asyncio
async def test_designer_can_start_and_stop_own_timer(client, tenants) -> None:
    tenant_a, _ = tenants
    _, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    headers = agency_headers(designer_token, tenant_a.agency_id)

    start_resp = await client.post(START_URL, json={"category": "design"}, headers=headers)
    assert start_resp.status_code == 201

    entry_id = start_resp.json()["id"]
    stop_resp = await client.post(f"/api/v1/time-entries/{entry_id}/stop", json={}, headers=headers)
    assert stop_resp.status_code == 200


@pytest.mark.asyncio
async def test_viewer_cannot_start_timer(client, tenants) -> None:
    tenant_a, _ = tenants
    _, viewer_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.VIEWER.value)
    headers = agency_headers(viewer_token, tenant_a.agency_id)

    resp = await client.post(START_URL, json={"category": "design"}, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_create_manual_entry(client, tenants) -> None:
    tenant_a, _ = tenants
    _, viewer_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.VIEWER.value)
    headers = agency_headers(viewer_token, tenant_a.agency_id)

    now = datetime.now(UTC) - timedelta(hours=2)
    resp = await client.post(
        MANUAL_URL,
        json={
            "category": "design",
            "started_at": now.isoformat(),
            "ended_at": (now + timedelta(hours=1)).isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_edit_own_entry(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    resp = await client.patch(
        f"/api/v1/time-entries/{tenant_a.time_entry_id}",
        json={"description": "Güncellenmiş açıklama"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Güncellenmiş açıklama"


@pytest.mark.asyncio
async def test_designer_cannot_edit_peer_entry_without_manage(client, tenants) -> None:
    """tenant_a.time_entry_id belongs to the ADMIN fixture user, not the
    newly-created DESIGNER — DESIGNER has TIME_ENTRY_LOG but not
    TIME_ENTRY_MANAGE, so editing someone else's entry must be refused."""
    tenant_a, _ = tenants
    _, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    headers = agency_headers(designer_token, tenant_a.agency_id)

    resp = await client.patch(
        f"/api/v1/time-entries/{tenant_a.time_entry_id}",
        json={"description": "should not be allowed"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_edit_peer_entry_with_manage(client, tenants) -> None:
    """ADMIN has TIME_ENTRY_MANAGE, so it can edit an entry created by
    another (DESIGNER) agency member."""
    tenant_a, _ = tenants
    designer_id, designer_token = await _add_agency_member(
        tenant_a.agency_id, AgencyMemberRole.DESIGNER.value
    )
    designer_headers = agency_headers(designer_token, tenant_a.agency_id)

    now = datetime.now(UTC) - timedelta(hours=3)
    create_resp = await client.post(
        MANUAL_URL,
        json={
            "category": "design",
            "started_at": now.isoformat(),
            "ended_at": (now + timedelta(hours=1)).isoformat(),
        },
        headers=designer_headers,
    )
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["entry"]["id"]

    admin_headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    edit_resp = await client.patch(
        f"/api/v1/time-entries/{entry_id}",
        json={"description": "Yönetici tarafından düzenlendi"},
        headers=admin_headers,
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["description"] == "Yönetici tarafından düzenlendi"


@pytest.mark.asyncio
async def test_brand_user_jwt_cannot_start_timer(client, tenants) -> None:
    tenant_a, _ = tenants
    resp = await client.post(
        START_URL,
        json={"category": "design"},
        headers={
            **brand_headers(tenant_a.brand_manager_token),
            "X-Agency-ID": str(tenant_a.agency_id),
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_brand_user_jwt_cannot_view_active_timer(client, tenants) -> None:
    tenant_a, _ = tenants
    resp = await client.get(
        "/api/v1/time-entries/active",
        headers={
            **brand_headers(tenant_a.brand_manager_token),
            "X-Agency-ID": str(tenant_a.agency_id),
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_brand_user_jwt_cannot_view_time_entry(client, tenants) -> None:
    tenant_a, _ = tenants
    resp = await client.get(
        f"/api/v1/time-entries/{tenant_a.time_entry_id}",
        headers={
            **brand_headers(tenant_a.brand_manager_token),
            "X-Agency-ID": str(tenant_a.agency_id),
        },
    )
    assert resp.status_code == 403

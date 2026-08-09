"""Locking tests: owner/admin (TIME_ENTRY_APPROVE) can lock a completed
entry, a locked entry then rejects any further edits, and a member without
TIME_ENTRY_APPROVE gets a 403 trying to lock."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.tests.conftest import agency_headers

MANUAL_URL = "/api/v1/time-entries"


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


def _lock_url(entry_id: str) -> str:
    return f"/api/v1/time-entries/{entry_id}/lock"


@pytest.mark.asyncio
async def test_admin_can_lock_completed_entry(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    resp = await client.post(_lock_url(str(tenant_a.time_entry_id)), headers=headers)
    assert resp.status_code == 200
    assert resp.json()["locked"] is True


@pytest.mark.asyncio
async def test_locked_entry_rejects_edits(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)

    lock_resp = await client.post(_lock_url(str(tenant_a.time_entry_id)), headers=headers)
    assert lock_resp.status_code == 200

    edit_resp = await client.patch(
        f"/api/v1/time-entries/{tenant_a.time_entry_id}",
        json={"description": "should be rejected"},
        headers=headers,
    )
    assert edit_resp.status_code == 409


@pytest.mark.asyncio
async def test_locked_entry_rejects_delete(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)

    lock_resp = await client.post(_lock_url(str(tenant_a.time_entry_id)), headers=headers)
    assert lock_resp.status_code == 200

    delete_resp = await client.delete(
        f"/api/v1/time-entries/{tenant_a.time_entry_id}", headers=headers
    )
    assert delete_resp.status_code == 409


@pytest.mark.asyncio
async def test_non_admin_designer_cannot_lock(client, tenants) -> None:
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
    entry_id = create_resp.json()["entry"]["id"]

    lock_resp = await client.post(_lock_url(entry_id), headers=designer_headers)
    assert lock_resp.status_code == 403


@pytest.mark.asyncio
async def test_locking_already_locked_entry_is_conflict(client, tenants) -> None:
    tenant_a, _ = tenants
    headers = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
    first = await client.post(_lock_url(str(tenant_a.time_entry_id)), headers=headers)
    assert first.status_code == 200

    second = await client.post(_lock_url(str(tenant_a.time_entry_id)), headers=headers)
    assert second.status_code == 409

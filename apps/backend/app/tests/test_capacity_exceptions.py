"""CapacityExceptionService tests: simple CRUD, one active exception per
(user, date), soft-delete freeing up the date for reuse, and tenant
isolation."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.schemas.capacity_exception import CapacityExceptionCreate, CapacityExceptionUpdate
from app.services.capacity_exception_service import CapacityExceptionService

TODAY = date.today()


async def _create_agency_with_user(label: str) -> tuple[uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        agency = Agency(
            id=uuid.uuid4(),
            name=f"{label} Agency",
            slug=f"{label.lower()}-agency-{suffix}",
        )
        session.add(agency)
        await session.flush()

        user = User(
            id=uuid.uuid4(),
            email=f"{label.lower()}-{suffix}@test.local",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name=f"Test {label}",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        session.add(
            AgencyMember(
                id=uuid.uuid4(),
                agency_id=agency.id,
                user_id=user.id,
                role=AgencyMemberRole.ADMIN.value,
                status=AgencyMemberStatus.ACTIVE.value,
            )
        )
        await session.commit()
        return agency.id, user.id


async def test_create_and_list_exception() -> None:
    agency_id, user_id = await _create_agency_with_user("CapExCreate")
    async with AsyncSessionLocal() as session:
        svc = CapacityExceptionService(session)
        created = await svc.create(
            agency_id,
            user_id,
            CapacityExceptionCreate(
                user_id=user_id,
                date=TODAY,
                capacity_minutes=240,
                exception_type="reduced",
                reason="Half day",
            ),
        )
        listed = await svc.list_for_user(agency_id, user_id)

    assert created.capacity_minutes == 240
    assert created.exception_type == "reduced"
    assert created.created_by_id == user_id
    assert len(listed) == 1
    assert listed[0].id == created.id


async def test_duplicate_exception_same_user_date_rejected() -> None:
    agency_id, user_id = await _create_agency_with_user("CapExDup")
    async with AsyncSessionLocal() as session:
        svc = CapacityExceptionService(session)
        await svc.create(
            agency_id,
            user_id,
            CapacityExceptionCreate(
                user_id=user_id, date=TODAY, capacity_minutes=0, exception_type="closure"
            ),
        )
        with pytest.raises(ConflictError):
            await svc.create(
                agency_id,
                user_id,
                CapacityExceptionCreate(
                    user_id=user_id,
                    date=TODAY,
                    capacity_minutes=480,
                    exception_type="increased",
                ),
            )


async def test_update_exception_changes_only_provided_fields() -> None:
    agency_id, user_id = await _create_agency_with_user("CapExUpdate")
    async with AsyncSessionLocal() as session:
        svc = CapacityExceptionService(session)
        created = await svc.create(
            agency_id,
            user_id,
            CapacityExceptionCreate(
                user_id=user_id,
                date=TODAY,
                capacity_minutes=240,
                exception_type="reduced",
                reason="Half day",
            ),
        )
        updated = await svc.update(
            agency_id, created.id, CapacityExceptionUpdate(capacity_minutes=120)
        )

    assert updated.capacity_minutes == 120
    assert updated.reason == "Half day"
    assert updated.exception_type == "reduced"


async def test_delete_soft_deletes_and_frees_the_date_for_reuse() -> None:
    agency_id, user_id = await _create_agency_with_user("CapExDelete")
    async with AsyncSessionLocal() as session:
        svc = CapacityExceptionService(session)
        created = await svc.create(
            agency_id,
            user_id,
            CapacityExceptionCreate(
                user_id=user_id, date=TODAY, capacity_minutes=240, exception_type="reduced"
            ),
        )
        await svc.delete(agency_id, created.id)
        listed = await svc.list_for_user(agency_id, user_id)
    assert listed == []

    async with AsyncSessionLocal() as session:
        recreated = await CapacityExceptionService(session).create(
            agency_id,
            user_id,
            CapacityExceptionCreate(
                user_id=user_id, date=TODAY, capacity_minutes=480, exception_type="increased"
            ),
        )
    assert recreated.capacity_minutes == 480


async def test_update_missing_exception_raises_not_found() -> None:
    agency_id, _ = await _create_agency_with_user("CapExMissing")
    async with AsyncSessionLocal() as session:
        with pytest.raises(NotFoundError):
            await CapacityExceptionService(session).update(
                agency_id, uuid.uuid4(), CapacityExceptionUpdate(capacity_minutes=1)
            )


async def test_exceptions_are_tenant_isolated() -> None:
    agency_a, user_a = await _create_agency_with_user("CapExTenantA")
    agency_b, _ = await _create_agency_with_user("CapExTenantB")

    async with AsyncSessionLocal() as session:
        created = await CapacityExceptionService(session).create(
            agency_a,
            user_a,
            CapacityExceptionCreate(
                user_id=user_a, date=TODAY, capacity_minutes=240, exception_type="reduced"
            ),
        )

    async with AsyncSessionLocal() as session:
        svc = CapacityExceptionService(session)
        with pytest.raises(NotFoundError):
            await svc.update(agency_b, created.id, CapacityExceptionUpdate(capacity_minutes=1))
        with pytest.raises(NotFoundError):
            await svc.delete(agency_b, created.id)

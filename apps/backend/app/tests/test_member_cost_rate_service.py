"""MemberCostRateService tests: one-open-ended-rate-per-user (and per-role)
enforcement/supersede, role-vs-user exclusivity, and the service-layer
Owner-only visibility gate (defense-in-depth on top of RBAC, plan §3/§6/§13)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.exceptions import PermissionDeniedError, ValidationError
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.commercial_terms import MemberCostRate
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.schemas.member_cost_rate import MemberCostRateCreate, MemberCostRateUpdate
from app.services.member_cost_rate_service import MemberCostRateService

TODAY = date.today()


async def _create_agency_with_user(label: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Returns (agency_id, owner_user_id, target_member_user_id)."""
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        agency = Agency(id=uuid.uuid4(), name=f"{label} Agency", slug=f"{label.lower()}-{suffix}")
        session.add(agency)
        await session.flush()

        owner = User(
            id=uuid.uuid4(),
            email=f"{label.lower()}-owner-{suffix}@test.local",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name=f"Test {label} Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        target = User(
            id=uuid.uuid4(),
            email=f"{label.lower()}-designer-{suffix}@test.local",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name=f"Test {label} Designer",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        session.add_all([owner, target])
        await session.flush()
        session.add_all(
            [
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=owner.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=target.id,
                    role=AgencyMemberRole.DESIGNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
            ]
        )
        await session.commit()
        return agency.id, owner.id, target.id


OWNER_ROLE = AgencyMemberRole.OWNER.value
ADMIN_ROLE = AgencyMemberRole.ADMIN.value


async def test_owner_can_create_cost_rate_for_user() -> None:
    agency_id, owner_id, target_id = await _create_agency_with_user("MCRCreate")
    async with AsyncSessionLocal() as session:
        obj, superseded = await MemberCostRateService(session).create(
            agency_id,
            owner_id,
            OWNER_ROLE,
            MemberCostRateCreate(
                user_id=target_id, currency="TRY", hourly_cost_cents=25000, valid_from=TODAY
            ),
        )
    assert obj.user_id == target_id
    assert obj.active is True
    assert superseded is None


async def test_admin_cannot_view_or_manage_cost_rates() -> None:
    """Plan §8: Admin explicitly does NOT get COST_RATE_VIEW/MANAGE — the
    service layer must reject even if somehow reached (defense-in-depth
    beyond the RBAC permission gate)."""
    agency_id, _, target_id = await _create_agency_with_user("MCRAdminBlocked")
    async with AsyncSessionLocal() as session:
        with pytest.raises(PermissionDeniedError):
            await MemberCostRateService(session).create(
                agency_id,
                uuid.uuid4(),
                ADMIN_ROLE,
                MemberCostRateCreate(
                    user_id=target_id, currency="TRY", hourly_cost_cents=25000, valid_from=TODAY
                ),
            )


async def test_designer_role_cannot_list_cost_rates() -> None:
    agency_id, _, target_id = await _create_agency_with_user("MCRDesignerBlocked")
    async with AsyncSessionLocal() as session:
        with pytest.raises(PermissionDeniedError):
            await MemberCostRateService(session).list_for_user(
                agency_id, target_id, AgencyMemberRole.DESIGNER.value
            )


async def test_creating_new_open_ended_rate_supersedes_prior_one() -> None:
    agency_id, owner_id, target_id = await _create_agency_with_user("MCRSupersede")
    async with AsyncSessionLocal() as session:
        svc = MemberCostRateService(session)
        first, _ = await svc.create(
            agency_id,
            owner_id,
            OWNER_ROLE,
            MemberCostRateCreate(
                user_id=target_id, currency="TRY", hourly_cost_cents=20000, valid_from=TODAY
            ),
        )

    async with AsyncSessionLocal() as session:
        svc = MemberCostRateService(session)
        second, superseded_id = await svc.create(
            agency_id,
            owner_id,
            OWNER_ROLE,
            MemberCostRateCreate(
                user_id=target_id,
                currency="TRY",
                hourly_cost_cents=30000,
                valid_from=TODAY + timedelta(days=30),
            ),
        )

    assert superseded_id == first.id
    assert second.active is True

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MemberCostRate).where(MemberCostRate.id == first.id))
        old_row = result.scalar_one()
    assert old_row.active is False
    assert old_row.valid_until == TODAY + timedelta(days=29)


async def test_only_one_open_ended_rate_survives_repeated_creates() -> None:
    agency_id, owner_id, target_id = await _create_agency_with_user("MCRSingleOpenEnded")
    async with AsyncSessionLocal() as session:
        svc = MemberCostRateService(session)
        for i in range(3):
            await svc.create(
                agency_id,
                owner_id,
                OWNER_ROLE,
                MemberCostRateCreate(
                    user_id=target_id,
                    currency="TRY",
                    hourly_cost_cents=20000 + i * 1000,
                    valid_from=TODAY + timedelta(days=i * 10),
                ),
            )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MemberCostRate).where(
                MemberCostRate.agency_id == agency_id,
                MemberCostRate.user_id == target_id,
                MemberCostRate.active.is_(True),
                MemberCostRate.valid_until.is_(None),
            )
        )
        open_ended_active = result.scalars().all()
    assert len(open_ended_active) == 1


async def test_role_based_rate_is_independent_of_user_based_rate() -> None:
    """A per-role fallback rate and a per-user override rate must never
    collide with each other's one-open-ended-rate enforcement — they are
    exclusive targets (schema-level `CheckConstraint`) with independent
    partial unique indexes."""
    agency_id, owner_id, target_id = await _create_agency_with_user("MCRRoleVsUser")
    async with AsyncSessionLocal() as session:
        svc = MemberCostRateService(session)
        user_rate, _ = await svc.create(
            agency_id,
            owner_id,
            OWNER_ROLE,
            MemberCostRateCreate(
                user_id=target_id, currency="TRY", hourly_cost_cents=25000, valid_from=TODAY
            ),
        )
        role_rate, _ = await svc.create(
            agency_id,
            owner_id,
            OWNER_ROLE,
            MemberCostRateCreate(
                role=AgencyMemberRole.DESIGNER.value,
                currency="TRY",
                hourly_cost_cents=18000,
                valid_from=TODAY,
            ),
        )

    assert user_rate.active is True
    assert role_rate.active is True


def test_exactly_one_of_user_or_role_is_enforced_by_schema() -> None:
    with pytest.raises(ValueError):
        MemberCostRateCreate(
            user_id=uuid.uuid4(),
            role=AgencyMemberRole.DESIGNER.value,
            currency="TRY",
            hourly_cost_cents=20000,
            valid_from=TODAY,
        )
    with pytest.raises(ValueError):
        MemberCostRateCreate(currency="TRY", hourly_cost_cents=20000, valid_from=TODAY)


def test_non_positive_hourly_cost_is_rejected_by_schema() -> None:
    with pytest.raises(ValueError):
        MemberCostRateCreate(
            user_id=uuid.uuid4(), currency="TRY", hourly_cost_cents=0, valid_from=TODAY
        )


async def test_non_positive_hourly_cost_is_rejected_by_service_defense_in_depth() -> None:
    agency_id, owner_id, target_id = await _create_agency_with_user("MCRServiceDefense")
    payload = MemberCostRateCreate(
        user_id=target_id, currency="TRY", hourly_cost_cents=1000, valid_from=TODAY
    )
    payload.hourly_cost_cents = -1  # bypass schema validation on purpose
    async with AsyncSessionLocal() as session:
        with pytest.raises(ValidationError):
            await MemberCostRateService(session).create(agency_id, owner_id, OWNER_ROLE, payload)


def test_invalid_currency_is_rejected_by_schema() -> None:
    with pytest.raises(ValueError):
        MemberCostRateCreate(
            user_id=uuid.uuid4(), currency="ZZZ", hourly_cost_cents=20000, valid_from=TODAY
        )


async def test_update_requires_owner_role() -> None:
    agency_id, owner_id, target_id = await _create_agency_with_user("MCRUpdateGate")
    async with AsyncSessionLocal() as session:
        svc = MemberCostRateService(session)
        obj, _ = await svc.create(
            agency_id,
            owner_id,
            OWNER_ROLE,
            MemberCostRateCreate(
                user_id=target_id, currency="TRY", hourly_cost_cents=20000, valid_from=TODAY
            ),
        )

    async with AsyncSessionLocal() as session:
        with pytest.raises(PermissionDeniedError):
            await MemberCostRateService(session).update(
                agency_id,
                obj.id,
                AgencyMemberRole.BRAND_MANAGER.value,
                MemberCostRateUpdate(hourly_cost_cents=22000),
            )


async def test_member_cost_rates_are_tenant_isolated() -> None:
    agency_a, owner_a, target_a = await _create_agency_with_user("MCRTenantA")
    agency_b, _, _ = await _create_agency_with_user("MCRTenantB")

    async with AsyncSessionLocal() as session:
        await MemberCostRateService(session).create(
            agency_a,
            owner_a,
            OWNER_ROLE,
            MemberCostRateCreate(
                user_id=target_a, currency="TRY", hourly_cost_cents=20000, valid_from=TODAY
            ),
        )

    async with AsyncSessionLocal() as session:
        cross_tenant = await MemberCostRateService(session).list_for_user(
            agency_b, target_a, OWNER_ROLE
        )
    assert cross_tenant == []

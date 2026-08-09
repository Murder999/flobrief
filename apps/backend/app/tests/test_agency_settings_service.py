"""AgencySettingsService tests: get-or-create idempotency, default values
(60/85/100/"TRY"/30/0/False), update persistence, and tenant isolation
across two independently-seeded agencies."""

from __future__ import annotations

import uuid

import pytest

from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.schemas.agency_settings import AgencySettingsUpdate
from app.services.agency_settings_service import AgencySettingsService


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


async def test_get_or_create_returns_documented_defaults_on_first_call() -> None:
    agency_id, _ = await _create_agency_with_user("SettingsDefaults")
    async with AsyncSessionLocal() as session:
        svc = AgencySettingsService(session)
        settings = await svc.get_or_create(agency_id)

    assert settings.agency_id == agency_id
    assert settings.capacity_available_threshold_pct == 60
    assert settings.capacity_balanced_threshold_pct == 85
    assert settings.capacity_near_threshold_pct == 100
    assert settings.default_currency == "TRY"
    assert settings.default_payment_terms_days == 30
    assert settings.invoice_number_seq == 0
    assert settings.retainer_default_rollover is False


async def test_get_or_create_is_idempotent() -> None:
    agency_id, _ = await _create_agency_with_user("SettingsIdempotent")
    async with AsyncSessionLocal() as session:
        first = await AgencySettingsService(session).get_or_create(agency_id)
    async with AsyncSessionLocal() as session:
        second = await AgencySettingsService(session).get_or_create(agency_id)
    async with AsyncSessionLocal() as session:
        third = await AgencySettingsService(session).get_or_create(agency_id)

    assert first.id == second.id == third.id


async def test_update_persists_changed_fields_only() -> None:
    agency_id, user_id = await _create_agency_with_user("SettingsUpdate")
    async with AsyncSessionLocal() as session:
        svc = AgencySettingsService(session)
        await svc.get_or_create(agency_id)
        updated = await svc.update(
            agency_id,
            AgencySettingsUpdate(default_currency="USD", default_payment_terms_days=45),
            updated_by_id=user_id,
        )

    assert updated.default_currency == "USD"
    assert updated.default_payment_terms_days == 45
    assert updated.updated_by_id == user_id
    # untouched fields keep their defaults
    assert updated.capacity_available_threshold_pct == 60
    assert updated.retainer_default_rollover is False


def test_threshold_ordering_validator_rejects_out_of_order_thresholds() -> None:
    with pytest.raises(ValueError):
        AgencySettingsUpdate(
            capacity_available_threshold_pct=90,
            capacity_balanced_threshold_pct=85,
            capacity_near_threshold_pct=100,
        )


def test_threshold_ordering_validator_allows_equal_thresholds() -> None:
    # boundary case: equal thresholds are a degenerate-but-valid ordering
    update = AgencySettingsUpdate(
        capacity_available_threshold_pct=60,
        capacity_balanced_threshold_pct=60,
        capacity_near_threshold_pct=100,
    )
    assert update.capacity_balanced_threshold_pct == 60


async def test_settings_are_tenant_isolated() -> None:
    agency_a, user_a = await _create_agency_with_user("SettingsTenantA")
    agency_b, _ = await _create_agency_with_user("SettingsTenantB")

    async with AsyncSessionLocal() as session:
        svc = AgencySettingsService(session)
        settings_a = await svc.get_or_create(agency_a)
        await svc.update(
            agency_a, AgencySettingsUpdate(default_currency="USD"), updated_by_id=user_a
        )

    async with AsyncSessionLocal() as session:
        settings_b = await AgencySettingsService(session).get_or_create(agency_b)

    assert settings_a.agency_id != settings_b.agency_id
    assert settings_b.default_currency == "TRY", "agency B must not see agency A's update"

"""CommercialTermsService tests: one-active-per-brand enforcement/supersede,
currency validation, negative-amount rejection, tax-rate range, and
overlapping-date-range rejection for historical rows (plan §3/§13)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.exceptions import ConflictError, ValidationError
from app.db.session import AsyncSessionLocal
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.commercial_terms import CommercialTerms
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.schemas.commercial_terms import CommercialTermsCreate, CommercialTermsUpdate
from app.services.commercial_terms_service import CommercialTermsService

TODAY = date.today()


async def _create_agency_with_brand(label: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:10]
        agency = Agency(id=uuid.uuid4(), name=f"{label} Agency", slug=f"{label.lower()}-{suffix}")
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name=f"{label} Brand",
            slug=f"{label.lower()}-brand-{suffix}",
        )
        session.add_all([agency, brand])
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
                role=AgencyMemberRole.OWNER.value,
                status=AgencyMemberStatus.ACTIVE.value,
            )
        )
        await session.commit()
        return agency.id, brand.id, user.id


def _create_payload(**overrides) -> CommercialTermsCreate:
    base = {
        "brand_id": uuid.uuid4(),
        "billing_model": "hourly",
        "currency": "TRY",
        "hourly_rate_cents": 50000,
        "payment_terms_days": 30,
        "tax_rate_bps": 2000,
        "valid_from": TODAY,
    }
    base.update(overrides)
    return CommercialTermsCreate(**base)


async def test_create_sets_active_term() -> None:
    agency_id, brand_id, user_id = await _create_agency_with_brand("CTCreate")
    async with AsyncSessionLocal() as session:
        obj, superseded = await CommercialTermsService(session).create(
            agency_id, user_id, _create_payload(brand_id=brand_id)
        )
    assert obj.active is True
    assert obj.brand_id == brand_id
    assert superseded is None


async def test_creating_new_term_supersedes_prior_active_term() -> None:
    agency_id, brand_id, user_id = await _create_agency_with_brand("CTSupersede")
    async with AsyncSessionLocal() as session:
        svc = CommercialTermsService(session)
        first, _ = await svc.create(agency_id, user_id, _create_payload(brand_id=brand_id))

    async with AsyncSessionLocal() as session:
        svc = CommercialTermsService(session)
        second, superseded_id = await svc.create(
            agency_id,
            user_id,
            _create_payload(
                brand_id=brand_id,
                billing_model="retainer",
                retainer_amount_cents=100000,
                hourly_rate_cents=None,
                valid_from=TODAY + timedelta(days=10),
            ),
        )

    assert superseded_id == first.id
    assert second.active is True

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CommercialTerms).where(CommercialTerms.id == first.id)
        )
        old_row = result.scalar_one()
    assert old_row.active is False
    assert old_row.valid_until == TODAY + timedelta(days=9)


async def test_only_one_active_term_survives_repeated_creates() -> None:
    agency_id, brand_id, user_id = await _create_agency_with_brand("CTSingleActive")
    async with AsyncSessionLocal() as session:
        svc = CommercialTermsService(session)
        for i in range(3):
            await svc.create(
                agency_id,
                user_id,
                _create_payload(brand_id=brand_id, valid_from=TODAY + timedelta(days=i * 30)),
            )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CommercialTerms).where(
                CommercialTerms.agency_id == agency_id,
                CommercialTerms.brand_id == brand_id,
                CommercialTerms.active.is_(True),
            )
        )
        active_rows = result.scalars().all()
    assert len(active_rows) == 1


def test_invalid_currency_is_rejected() -> None:
    with pytest.raises(ValueError):
        _create_payload(currency="XXX")


def test_negative_amount_is_rejected_by_schema() -> None:
    with pytest.raises(ValueError):
        _create_payload(hourly_rate_cents=-100)


async def test_negative_amount_is_rejected_by_service_defense_in_depth() -> None:
    """Bypasses the Pydantic schema entirely to prove the service itself
    re-validates — construct the schema with a valid value, then hand the
    service a dict with a negative amount smuggled in past the schema."""
    agency_id, brand_id, user_id = await _create_agency_with_brand("CTServiceDefense")
    payload = _create_payload(brand_id=brand_id)
    payload.hourly_rate_cents = -500  # bypass schema validation on purpose
    async with AsyncSessionLocal() as session:
        with pytest.raises(ValidationError):
            await CommercialTermsService(session).create(agency_id, user_id, payload)


def test_tax_rate_out_of_range_is_rejected_by_schema() -> None:
    with pytest.raises(ValueError):
        _create_payload(tax_rate_bps=10001)


def test_valid_until_before_valid_from_is_rejected() -> None:
    with pytest.raises(ValueError):
        _create_payload(valid_from=TODAY, valid_until=TODAY - timedelta(days=1))


async def test_create_rejects_date_range_overlapping_a_historical_row() -> None:
    """Plan §3: "overlapping-date-range validation for non-active/historical
    rows happens in CommercialTermsService, not the DB" — two inactive
    (historical) rows for the same brand that don't overlap each other are
    fine, but a new row whose range falls inside one of them must be
    rejected even though neither is `active` (so the DB's partial unique
    index alone would never catch it)."""
    agency_id, brand_id, user_id = await _create_agency_with_brand("CTOverlap")
    from app.repositories.commercial_terms import CommercialTermsRepository

    async with AsyncSessionLocal() as session:
        repo = CommercialTermsRepository(session)
        await repo.create(
            {
                "agency_id": agency_id,
                "brand_id": brand_id,
                "billing_model": "hourly",
                "currency": "TRY",
                "hourly_rate_cents": 40000,
                "payment_terms_days": 30,
                "tax_rate_bps": 2000,
                "valid_from": TODAY,
                "valid_until": TODAY + timedelta(days=10),
                "active": False,
                "created_by_id": user_id,
            }
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        svc = CommercialTermsService(session)
        with pytest.raises(ConflictError):
            await svc.create(
                agency_id,
                user_id,
                _create_payload(
                    brand_id=brand_id,
                    valid_from=TODAY + timedelta(days=5),
                    valid_until=TODAY + timedelta(days=15),
                ),
            )


async def test_update_changes_fields_and_revalidates() -> None:
    agency_id, brand_id, user_id = await _create_agency_with_brand("CTUpdate")
    async with AsyncSessionLocal() as session:
        svc = CommercialTermsService(session)
        obj, _ = await svc.create(agency_id, user_id, _create_payload(brand_id=brand_id))

    async with AsyncSessionLocal() as session:
        svc = CommercialTermsService(session)
        updated = await svc.update(
            agency_id, obj.id, user_id, CommercialTermsUpdate(tax_rate_bps=1800)
        )
    assert updated.tax_rate_bps == 1800

    async with AsyncSessionLocal() as session:
        svc = CommercialTermsService(session)
        bad_update = CommercialTermsUpdate(tax_rate_bps=5000)
        bad_update.tax_rate_bps = 99999  # bypass schema validation on purpose
        with pytest.raises(ValidationError):
            await svc.update(agency_id, obj.id, user_id, bad_update)


async def test_get_active_for_brand_returns_none_when_no_term_exists() -> None:
    agency_id, brand_id, _ = await _create_agency_with_brand("CTNoTerm")
    async with AsyncSessionLocal() as session:
        active = await CommercialTermsService(session).get_active_for_brand(agency_id, brand_id)
    assert active is None


async def test_commercial_terms_are_tenant_isolated() -> None:
    agency_a, brand_a, user_a = await _create_agency_with_brand("CTTenantA")
    agency_b, _, _ = await _create_agency_with_brand("CTTenantB")

    async with AsyncSessionLocal() as session:
        await CommercialTermsService(session).create(
            agency_a, user_a, _create_payload(brand_id=brand_a)
        )

    async with AsyncSessionLocal() as session:
        cross_tenant = await CommercialTermsService(session).get_active_for_brand(agency_b, brand_a)
    assert cross_tenant is None

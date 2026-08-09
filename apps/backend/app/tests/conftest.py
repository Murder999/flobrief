import os

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-flobrief-64-chars-xxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://flobrief:flobrief@localhost:5433/flobrief_test"
)

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.brief import Brief
from app.models.deliverable import Deliverable
from app.models.deliverable_annotation import DeliverableAnnotation
from app.models.enums import (
    AgencyMemberRole,
    AgencyMemberStatus,
    BrandMemberRole,
    BrandMemberStatus,
    UserType,
)
from app.models.time_entry import TimeEntry
from app.models.user import User


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def _dispose_db_engine_pool_after_test():
    """asyncpg connections are bound to the event loop that opened them.

    pytest-asyncio tears down a fresh event loop per test function, but
    SQLAlchemy's connection pool (app.db.session.engine) is a module-level
    singleton that would otherwise hand out pooled connections from a closed
    loop to the next live-DB test. Disposing it here, inside the still-open
    loop, forces a clean reconnect per test instead of that cross-loop reuse
    crash. A no-op for tests that never touch the DB.
    """
    yield
    from app.db.session import engine

    await engine.dispose()


@pytest.fixture(autouse=True)
async def _reset_redis_client_after_test():
    """Same cross-loop-reuse problem as the DB engine pool above, but for the
    rate limiter's module-level redis.asyncio.Redis singleton: a connection
    opened against one test's event loop breaks silently on the next test's
    loop, and the rate limiter's fail-open path swallows that as "Redis
    unavailable" instead of surfacing it. Resetting the singleton forces a
    fresh connection per test."""
    yield
    import app.core.rate_limiter as rate_limiter_module

    if rate_limiter_module._redis_client is not None:
        await rate_limiter_module._redis_client.aclose()
        rate_limiter_module._redis_client = None


# ── Two-tenant annotation fixture ────────────────────────────────────────────
#
# Shared by test_annotation_tenant_isolation.py and test_annotation_notifications.py.
# Lives in conftest.py (not a plain module import between test files) so pytest
# auto-discovers the `tenants` fixture without triggering ruff F811
# (redefinition-via-import) on the fixture name in every consuming module.


def agency_headers(token: str, agency_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Agency-ID": str(agency_id)}


def brand_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass
class Tenant:
    agency_id: uuid.UUID
    brand_id: uuid.UUID
    agency_user_id: uuid.UUID
    agency_token: str
    brand_manager_id: uuid.UUID
    brand_manager_token: str
    brand_viewer_id: uuid.UUID
    brand_viewer_token: str
    brief_id: uuid.UUID
    deliverable_id: uuid.UUID
    annotation_id: uuid.UUID  # client_visible, status=resolved on `deliverable_id`
    other_brief_id: uuid.UUID
    other_deliverable_id: uuid.UUID  # unrelated deliverable, same tenant, no annotations
    time_entry_id: uuid.UUID  # stopped, unlocked, billable "design"-category entry


def _token(user_id: uuid.UUID) -> str:
    return create_access_token(str(user_id))


async def _make_user(session, email: str, user_type: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash="not-a-real-hash-test-fixture-only",
        full_name="Test Fixture User",
        user_type=user_type,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    return user


async def _build_tenant(session, label: str) -> Tenant:
    suffix = uuid.uuid4().hex[:10]

    agency = Agency(
        id=uuid.uuid4(), name=f"{label} Agency", slug=f"{label.lower()}-agency-{suffix}"
    )
    brand = Brand(
        id=uuid.uuid4(),
        agency_id=agency.id,
        name=f"{label} Brand",
        slug=f"{label.lower()}-brand-{suffix}",
    )
    session.add_all([agency, brand])

    email_prefix = f"{label.lower()}-{suffix}"
    agency_user = await _make_user(
        session, f"{email_prefix}-agency@test.local", UserType.AGENCY_USER.value
    )
    brand_manager = await _make_user(
        session, f"{email_prefix}-brandmgr@test.local", UserType.BRAND_USER.value
    )
    brand_viewer = await _make_user(
        session, f"{email_prefix}-brandviewer@test.local", UserType.BRAND_USER.value
    )

    await session.flush()  # assign PKs referenced by FK rows below

    session.add_all(
        [
            AgencyMember(
                id=uuid.uuid4(),
                agency_id=agency.id,
                user_id=agency_user.id,
                role=AgencyMemberRole.ADMIN.value,
                status=AgencyMemberStatus.ACTIVE.value,
            ),
            BrandMember(
                id=uuid.uuid4(),
                brand_id=brand.id,
                user_id=brand_manager.id,
                role=BrandMemberRole.BRAND_MANAGER.value,
                status=BrandMemberStatus.ACTIVE.value,
            ),
            BrandMember(
                id=uuid.uuid4(),
                brand_id=brand.id,
                user_id=brand_viewer.id,
                role=BrandMemberRole.BRAND_VIEWER.value,
                status=BrandMemberStatus.ACTIVE.value,
            ),
        ]
    )

    brief = Brief(
        id=uuid.uuid4(),
        agency_id=agency.id,
        brand_id=brand.id,
        title=f"{label} Brief",
        status="draft",
        created_by_id=agency_user.id,
    )
    other_brief = Brief(
        id=uuid.uuid4(),
        agency_id=agency.id,
        brand_id=brand.id,
        title=f"{label} Other Brief",
        status="draft",
        created_by_id=agency_user.id,
    )
    session.add_all([brief, other_brief])
    await session.flush()

    deliverable = Deliverable(
        id=uuid.uuid4(),
        agency_id=agency.id,
        brand_id=brand.id,
        brief_id=brief.id,
        title=f"{label} Deliverable",
        deliverable_type="image",
        status="submitted",
    )
    other_deliverable = Deliverable(
        id=uuid.uuid4(),
        agency_id=agency.id,
        brand_id=brand.id,
        brief_id=other_brief.id,
        title=f"{label} Other Deliverable",
        deliverable_type="image",
        status="submitted",
    )
    session.add_all([deliverable, other_deliverable])
    await session.flush()

    annotation = DeliverableAnnotation(
        id=uuid.uuid4(),
        agency_id=agency.id,
        brand_id=brand.id,
        brief_id=brief.id,
        deliverable_id=deliverable.id,
        version_number=1,
        label_number=1,
        status="resolved",
        annotation_type="revision",
        visibility="client_visible",
        body=f"{label} revision note",
        created_by_id=brand_manager.id,
        resolved_by_id=agency_user.id,
        resolved_at=datetime.now(UTC),
    )
    session.add(annotation)

    time_entry_started = datetime.now(UTC) - timedelta(hours=2)
    time_entry_ended = datetime.now(UTC) - timedelta(hours=1)
    time_entry = TimeEntry(
        id=uuid.uuid4(),
        agency_id=agency.id,
        brand_id=brand.id,
        brief_id=brief.id,
        user_id=agency_user.id,
        category="design",
        description=f"{label} fixture time entry",
        started_at=time_entry_started,
        ended_at=time_entry_ended,
        duration_seconds=int((time_entry_ended - time_entry_started).total_seconds()),
        billable=True,
        source="manual",
        locked=False,
    )
    session.add(time_entry)
    await session.commit()

    return Tenant(
        agency_id=agency.id,
        brand_id=brand.id,
        agency_user_id=agency_user.id,
        agency_token=_token(agency_user.id),
        brand_manager_id=brand_manager.id,
        brand_manager_token=_token(brand_manager.id),
        brand_viewer_id=brand_viewer.id,
        brand_viewer_token=_token(brand_viewer.id),
        brief_id=brief.id,
        deliverable_id=deliverable.id,
        annotation_id=annotation.id,
        other_brief_id=other_brief.id,
        other_deliverable_id=other_deliverable.id,
        time_entry_id=time_entry.id,
    )


async def _cleanup_tenant(session, tenant: Tenant) -> None:
    # Agency delete cascades: agency_members, briefs -> deliverables ->
    # deliverable_annotations -> annotation_replies (all ON DELETE CASCADE).
    agency = await session.get(Agency, tenant.agency_id)
    if agency is not None:
        await session.delete(agency)
    brand = await session.get(Brand, tenant.brand_id)
    if brand is not None:
        await session.delete(brand)  # cascades brand_members
    await session.commit()

    for user_id in (tenant.agency_user_id, tenant.brand_manager_id, tenant.brand_viewer_id):
        user = await session.get(User, user_id)
        if user is not None:
            await session.delete(user)
    await session.commit()


@pytest.fixture
async def tenants():
    """Two independent, fully-seeded tenants (agency + brand + users + brief +
    deliverable + one resolved client_visible annotation each), for IDOR /
    tenant-isolation / reopen-authorization / notification tests."""
    async with AsyncSessionLocal() as session:
        tenant_a = await _build_tenant(session, "TenantA")
        tenant_b = await _build_tenant(session, "TenantB")
        try:
            yield tenant_a, tenant_b
        finally:
            await _cleanup_tenant(session, tenant_a)
            await _cleanup_tenant(session, tenant_b)

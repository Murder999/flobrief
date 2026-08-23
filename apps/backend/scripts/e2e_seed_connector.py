"""E2E fixture for e2e/accounting-connector-flow.spec.ts.

Creates one Agency + a Brand + one owner AgencyMember (the only role with
ACCOUNTING_INTEGRATION_MANAGE). No AccountingConnector row is pre-seeded --
the spec itself configures the manual connector and runs test-connection
through the real browser UI/backend, so the "connected" status asserted
below comes from a real synchronous ManualConnector.test_connection() call,
never a fabricated success.

Two modes:
  python e2e_seed_connector.py seed            -> prints E2E_* env vars
  python e2e_seed_connector.py cleanup <agency_id>

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production" -- mirrors e2e_seed_time_tracking.py.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.agency import Agency  # noqa: E402
from app.models.agency_member import AgencyMember  # noqa: E402
from app.models.brand import Brand  # noqa: E402
from app.models.enums import (  # noqa: E402
    AgencyMemberRole,
    AgencyMemberStatus,
    AgencyStatus,
    BrandStatus,
    UserType,
)
from app.models.user import User  # noqa: E402

OWNER_EMAIL = "flobrief-e2e-connector-owner@example.com"
PASSWORD = "E2eTest1234!"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _assert_local_test_database() -> None:
    host = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing to run: DATABASE_URL host {host!r} is not a local host {_LOCAL_HOSTS}."
        )
    if settings.is_production:
        raise RuntimeError("Refusing to run: APP_ENV=production.")


async def cleanup_by_email() -> None:
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == OWNER_EMAIL))
        ).scalar_one_or_none()
        if user is not None:
            member = (
                await db.execute(select(AgencyMember).where(AgencyMember.user_id == user.id))
            ).scalar_one_or_none()
            if member is not None:
                agency = await db.get(Agency, member.agency_id)
                if agency is not None:
                    await db.delete(agency)
                brands = (
                    (await db.execute(select(Brand).where(Brand.agency_id == member.agency_id)))
                    .scalars()
                    .all()
                )
                for brand in brands:
                    await db.delete(brand)
        await db.commit()

        user = (
            await db.execute(select(User).where(User.email == OWNER_EMAIL))
        ).scalar_one_or_none()
        if user is not None:
            await db.delete(user)
        await db.commit()


async def cleanup_by_agency_id(agency_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        agency = await db.get(Agency, agency_id)
        if agency is not None:
            await db.delete(agency)  # cascades agency_members/accounting_connectors/...
        brands = (
            (await db.execute(select(Brand).where(Brand.agency_id == agency_id))).scalars().all()
        )
        for brand in brands:
            await db.delete(brand)
        await db.commit()

        user = (
            await db.execute(select(User).where(User.email == OWNER_EMAIL))
        ).scalar_one_or_none()
        if user is not None:
            await db.delete(user)
        await db.commit()


async def seed_db() -> tuple[uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as db:
        agency = Agency(
            id=uuid.uuid4(),
            name="E2E Connector Agency",
            slug=f"e2e-connector-agency-{uuid.uuid4().hex[:8]}",
            status=AgencyStatus.ACTIVE.value,
        )
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name="E2E Connector Brand",
            slug=f"e2e-connector-brand-{uuid.uuid4().hex[:8]}",
            status=BrandStatus.ACTIVE.value,
        )
        db.add_all([agency, brand])

        owner = User(
            id=uuid.uuid4(),
            email=OWNER_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Connector Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        db.add(owner)
        await db.flush()

        db.add(
            AgencyMember(
                id=uuid.uuid4(),
                agency_id=agency.id,
                user_id=owner.id,
                role=AgencyMemberRole.OWNER.value,
                status=AgencyMemberStatus.ACTIVE.value,
            )
        )
        await db.commit()

        return agency.id, brand.id


async def main() -> None:
    _assert_local_test_database()

    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if mode == "cleanup":
        if len(sys.argv) > 2:
            await cleanup_by_agency_id(uuid.UUID(sys.argv[2]))
        else:
            await cleanup_by_email()
        print("cleaned up")
        return

    await cleanup_by_email()
    agency_id, brand_id = await seed_db()
    print("E2E_OWNER_EMAIL=" + OWNER_EMAIL)
    print("E2E_PASSWORD=" + PASSWORD)
    print("__AGENCY_ID__=" + str(agency_id))


if __name__ == "__main__":
    asyncio.run(main())

"""E2E fixture for apps/frontend/e2e/whatsapp-connection-flow.spec.ts.

Creates one Agency + agency owner User (opted in to WhatsApp, with a phone
number already set) and one Agency + agency VIEWER User (insufficient
permission to test-send) and one demo Agency + owner User (must never allow a
real test-send). Tracked, repeatable (cleanup-then-seed under fixed emails),
self-cleaning (`cleanup` mode) — mirrors e2e_seed_annotation_flow.py.

Two modes:
  python e2e_seed_whatsapp_connection_flow.py seed     -> prints E2E_* env vars
  python e2e_seed_whatsapp_connection_flow.py cleanup  -> deletes the fixture

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production".
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.agency import Agency  # noqa: E402
from app.models.agency_member import AgencyMember  # noqa: E402
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType  # noqa: E402
from app.models.notification import NotificationPreference  # noqa: E402
from app.models.user import User  # noqa: E402

OWNER_EMAIL = "flobrief-e2e-whatsapp-owner@example.com"
VIEWER_EMAIL = "flobrief-e2e-whatsapp-viewer@example.com"
DEMO_OWNER_EMAIL = "flobrief-e2e-whatsapp-demo-owner@example.com"
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


async def _delete_fixture(session) -> None:
    for email in (OWNER_EMAIL, VIEWER_EMAIL, DEMO_OWNER_EMAIL):
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            continue
        agencies = (
            (
                await session.execute(
                    select(Agency)
                    .join(AgencyMember, AgencyMember.agency_id == Agency.id)
                    .where(AgencyMember.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        for agency in agencies:
            await session.delete(agency)
        await session.flush()
        await session.delete(user)
    await session.commit()


async def cleanup() -> None:
    _assert_local_test_database()
    async with AsyncSessionLocal() as session:
        await _delete_fixture(session)
    print("Cleanup complete.")


async def seed() -> None:
    _assert_local_test_database()
    async with AsyncSessionLocal() as session:
        await _delete_fixture(session)

        pw_hash = hash_password(PASSWORD)

        owner_agency = Agency(name="E2E WhatsApp Agency", slug="e2e-whatsapp-agency", is_demo=False)
        owner_user = User(
            email=OWNER_EMAIL,
            password_hash=pw_hash,
            full_name="E2E WhatsApp Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
            phone_number="+905551234567",
            whatsapp_opt_in=True,
        )
        viewer_user = User(
            email=VIEWER_EMAIL,
            password_hash=pw_hash,
            full_name="E2E WhatsApp Viewer",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        now = datetime.now(UTC)
        demo_agency = Agency(
            name="E2E WhatsApp Demo Agency",
            slug="e2e-whatsapp-demo-agency",
            is_demo=True,
            demo_started_at=now,
            demo_expires_at=now + timedelta(days=7),
        )
        demo_owner_user = User(
            email=DEMO_OWNER_EMAIL,
            password_hash=pw_hash,
            full_name="E2E WhatsApp Demo Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
            phone_number="+905551234568",
            whatsapp_opt_in=True,
        )
        session.add_all([owner_agency, owner_user, viewer_user, demo_agency, demo_owner_user])
        await session.flush()

        session.add_all(
            [
                AgencyMember(
                    agency_id=owner_agency.id,
                    user_id=owner_user.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    agency_id=owner_agency.id,
                    user_id=viewer_user.id,
                    role=AgencyMemberRole.VIEWER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    agency_id=demo_agency.id,
                    user_id=demo_owner_user.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                NotificationPreference(user_id=owner_user.id, whatsapp_enabled=True),
                NotificationPreference(user_id=demo_owner_user.id, whatsapp_enabled=True),
            ]
        )
        await session.commit()

        print(f"E2E_OWNER_EMAIL={OWNER_EMAIL}")
        print(f"E2E_VIEWER_EMAIL={VIEWER_EMAIL}")
        print(f"E2E_DEMO_OWNER_EMAIL={DEMO_OWNER_EMAIL}")
        print(f"E2E_PASSWORD={PASSWORD}")
        print(f"E2E_AGENCY_ID={owner_agency.id}")
        print(f"E2E_DEMO_AGENCY_ID={demo_agency.id}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if mode == "cleanup":
        asyncio.run(cleanup())
    else:
        asyncio.run(seed())


if __name__ == "__main__":
    main()

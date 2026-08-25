"""E2E fixture for apps/frontend/e2e/whatsapp-preferences-flow.spec.ts (Part 6B-2).

Creates two independent agencies (for cross-tenant isolation checks), a brand
under agency A, and approves exactly one WhatsApp template
(`brief_created`) so the spec can assert both a "template ready" and a
"template missing" state without touching any other seeded template row.
Tracked, repeatable (cleanup-then-seed under fixed emails), self-cleaning —
mirrors e2e_seed_whatsapp_connection_flow.py.

Two modes:
  python e2e_seed_whatsapp_preferences_flow.py seed     -> prints E2E_* env vars
  python e2e_seed_whatsapp_preferences_flow.py cleanup  -> deletes the fixture

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production".
"""

from __future__ import annotations

import asyncio
import sys
import uuid
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
from app.models.brand import Brand  # noqa: E402
from app.models.brand_member import BrandMember  # noqa: E402
from app.models.enums import (  # noqa: E402
    AgencyMemberRole,
    AgencyMemberStatus,
    BrandMemberRole,
    BrandMemberStatus,
    NotificationEventType,
    UserType,
    WhatsAppTemplateStatus,
)
from app.models.notification import NotificationPreference  # noqa: E402
from app.models.platform_provider_settings import PlatformProviderSetting  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories.notification import NotificationPreferenceRepository  # noqa: E402
from app.repositories.whatsapp_template import WhatsAppTemplateRepository  # noqa: E402
from app.services.notification_dispatcher import NotificationDispatcher  # noqa: E402
from app.services.secret_encryption import secret_encryption  # noqa: E402

OWNER_A_EMAIL = "flobrief-e2e-waprefs-owner-a@example.com"
OWNER_B_EMAIL = "flobrief-e2e-waprefs-owner-b@example.com"
BRAND_MANAGER_EMAIL = "flobrief-e2e-waprefs-brandmgr@example.com"
DEMO_OWNER_EMAIL = "flobrief-e2e-waprefs-demo-owner@example.com"
PASSWORD = "E2eTest1234!"
READY_TEMPLATE_CODE = "brief_created"
E2E_PROVIDER_MARKER = "E2E1"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_ALL_EMAILS = (OWNER_A_EMAIL, OWNER_B_EMAIL, BRAND_MANAGER_EMAIL, DEMO_OWNER_EMAIL)


def _assert_local_test_database() -> None:
    host = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing to run: DATABASE_URL host {host!r} is not a local host {_LOCAL_HOSTS}."
        )
    if settings.is_production:
        raise RuntimeError("Refusing to run: APP_ENV=production.")


async def _delete_fixture(session) -> None:
    for email in _ALL_EMAILS:
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
        brands = (
            (
                await session.execute(
                    select(Brand)
                    .join(BrandMember, BrandMember.brand_id == Brand.id)
                    .where(BrandMember.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        for brand in brands:
            await session.delete(brand)
        await session.flush()
        await session.delete(user)

    provider = (
        await session.execute(
            select(PlatformProviderSetting).where(
                PlatformProviderSetting.provider == "whatsapp_twilio",
                PlatformProviderSetting.account_sid_last4 == E2E_PROVIDER_MARKER,
            )
        )
    ).scalar_one_or_none()
    if provider is not None:
        await session.delete(provider)
    await session.commit()

    # Restore the shared template row to its draft/no-content_sid baseline.
    repo = WhatsAppTemplateRepository(session)
    tpl = await repo.get_by_code(READY_TEMPLATE_CODE)
    if tpl is not None:
        tpl.status = WhatsAppTemplateStatus.DRAFT.value
        tpl.content_sid = None
        session.add(tpl)
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

        agency_a = Agency(name="E2E WA Prefs Agency A", slug="e2e-waprefs-agency-a", is_demo=False)
        agency_b = Agency(name="E2E WA Prefs Agency B", slug="e2e-waprefs-agency-b", is_demo=False)

        owner_a = User(
            email=OWNER_A_EMAIL,
            password_hash=pw_hash,
            full_name="E2E WA Prefs Owner A",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
            phone_number="+905551230001",
            locale="tr",
        )
        owner_b = User(
            email=OWNER_B_EMAIL,
            password_hash=pw_hash,
            full_name="E2E WA Prefs Owner B",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
            phone_number="+905551230002",
            locale="tr",
        )
        brand_manager = User(
            email=BRAND_MANAGER_EMAIL,
            password_hash=pw_hash,
            full_name="E2E WA Prefs Brand Manager",
            user_type=UserType.BRAND_USER.value,
            is_active=True,
            is_verified=True,
            phone_number="+905551230003",
            locale="tr",
        )
        now = datetime.now(UTC)
        demo_agency = Agency(
            name="E2E WA Prefs Demo Agency",
            slug="e2e-waprefs-demo-agency",
            is_demo=True,
            demo_started_at=now,
            demo_expires_at=now + timedelta(days=7),
        )
        demo_owner = User(
            email=DEMO_OWNER_EMAIL,
            password_hash=pw_hash,
            full_name="E2E WA Prefs Demo Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
            phone_number="+905551230004",
            locale="tr",
        )

        session.add_all(
            [agency_a, agency_b, demo_agency, owner_a, owner_b, brand_manager, demo_owner]
        )
        await session.flush()

        brand_a = Brand(agency_id=agency_a.id, name="E2E WA Prefs Brand", slug="e2e-waprefs-brand")
        session.add(brand_a)
        await session.flush()

        session.add_all(
            [
                AgencyMember(
                    agency_id=agency_a.id,
                    user_id=owner_a.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    agency_id=agency_b.id,
                    user_id=owner_b.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    agency_id=demo_agency.id,
                    user_id=demo_owner.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                BrandMember(
                    brand_id=brand_a.id,
                    user_id=brand_manager.id,
                    role=BrandMemberRole.BRAND_MANAGER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                ),
                NotificationPreference(user_id=demo_owner.id, whatsapp_enabled=True),
            ]
        )

        # Approve exactly one template so the UI can show both a "ready" and
        # a "missing" state without mutating any other seeded template row.
        template_repo = WhatsAppTemplateRepository(session)
        tpl = await template_repo.get_by_code(READY_TEMPLATE_CODE)
        assert tpl is not None, "migration seed must have created whatsapp_templates.brief_created"
        tpl.status = WhatsAppTemplateStatus.APPROVED.value
        tpl.content_sid = "HXe2efakecontentsid"
        session.add(tpl)
        await session.commit()

        # Give demo_owner consent so the demo test-send button is reachable.
        demo_owner.whatsapp_opt_in = True
        session.add(demo_owner)
        await session.commit()

        # Give owner_a a real WhatsApp delivery row (tenant-isolation check).
        pref_repo = NotificationPreferenceRepository(session)
        owner_a.whatsapp_opt_in = True
        session.add(owner_a)
        pref = await pref_repo.get_or_create(owner_a.id)
        await pref_repo.update(pref, email_enabled=True, whatsapp_enabled=True, in_app_enabled=True)
        await session.commit()

        await NotificationDispatcher(session).emit(
            NotificationEventType.BRIEF_CREATED.value,
            payload={"brief_id": str(uuid.uuid4()), "brief_title": "E2E Seed Brief"},
            agency_id=agency_a.id,
            brand_id=brand_a.id,
            actor_user_id=None,
            recipient_ids=[owner_a.id],
        )
        await session.commit()

        provider = (
            await session.execute(
                select(PlatformProviderSetting).where(
                    PlatformProviderSetting.provider == "whatsapp_twilio"
                )
            )
        ).scalar_one_or_none()
        if provider is None:
            session.add(
                PlatformProviderSetting(
                    provider="whatsapp_twilio",
                    provider_type="twilio_sandbox",
                    is_enabled=True,
                    encrypted_account_sid=secret_encryption.encrypt(
                        "AC00000000000000000000000000E2E1"
                    ),
                    encrypted_auth_token=secret_encryption.encrypt("e2e-local-only-token"),
                    encrypted_whatsapp_from=secret_encryption.encrypt("whatsapp:+15555550199"),
                    account_sid_last4=E2E_PROVIDER_MARKER,
                    whatsapp_from_masked="whatsapp:+1555****0199",
                    configured_at=datetime.now(UTC),
                )
            )
            await session.commit()

        print(f"E2E_OWNER_A_EMAIL={OWNER_A_EMAIL}")
        print(f"E2E_OWNER_B_EMAIL={OWNER_B_EMAIL}")
        print(f"E2E_BRAND_MANAGER_EMAIL={BRAND_MANAGER_EMAIL}")
        print(f"E2E_DEMO_OWNER_EMAIL={DEMO_OWNER_EMAIL}")
        print(f"E2E_PASSWORD={PASSWORD}")
        print(f"E2E_AGENCY_A_ID={agency_a.id}")
        print(f"E2E_AGENCY_B_ID={agency_b.id}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if mode == "cleanup":
        asyncio.run(cleanup())
    else:
        asyncio.run(seed())


if __name__ == "__main__":
    main()

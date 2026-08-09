"""E2E fixture for the Platform Admin / White Label / SEO / Profile-Security specs.

Creates:
  - 1 platform_admin user (no MFA) for login/profile/session/MFA specs
  - 1 normal agency user (for the "cannot access platform route" check)
  - 2 plans (one white_label_enabled, one not)
  - Agency A: white-label ENABLED + entitled, owner + admin member (role-change,
    last-owner-protection, plan-change targets), one brief+approval+public
    token so the real /approve/[token] portal page can be checked against its
    own override branding.
  - Agency B: white-label NOT configured (relies on platform defaults), owner
    member only, one brief+approval+public token to check the platform-default
    fallback on the same real portal page.
  - Platform branding defaults (portal name, primary color, footer) so both
    the White Label editor and the Agency-B fallback have real values.
  - One PlatformSeoPageSettings row for "home" with real metadata.

Two modes:
  python e2e_seed_platform_admin.py seed     -> prints E2E_* / __KEY__ env vars
  python e2e_seed_platform_admin.py cleanup <agency_a_id> <agency_b_id>
"""
from __future__ import annotations

import asyncio
import hashlib
import secrets
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.agency import Agency  # noqa: E402
from app.models.agency_member import AgencyMember  # noqa: E402
from app.models.approval import Approval, ApprovalToken, BriefVersion  # noqa: E402
from app.models.branding import AgencyBrandingSettings  # noqa: E402
from app.models.brief import Brief  # noqa: E402
from app.models.enums import (  # noqa: E402
    AgencyMemberRole,
    AgencyMemberStatus,
    AgencyStatus,
    UserType,
)
from app.models.plan import Plan  # noqa: E402
from app.models.platform_branding_defaults import PlatformBrandingDefaults  # noqa: E402
from app.models.platform_seo_settings import PlatformSeoPageSettings  # noqa: E402
from app.models.subscription import Subscription  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.user_mfa_recovery_code import UserMfaRecoveryCode  # noqa: E402
from app.models.user_token import UserToken  # noqa: E402

PLATFORM_ADMIN_EMAIL = "flobrief-e2e-platform-admin@example.com"
NORMAL_USER_EMAIL = "flobrief-e2e-platform-normaluser@example.com"
OWNER_A_EMAIL = "flobrief-e2e-platform-owner-a@example.com"
ADMIN_A_EMAIL = "flobrief-e2e-platform-admin-a@example.com"
OWNER_B_EMAIL = "flobrief-e2e-platform-owner-b@example.com"
PASSWORD = "E2eTest1234!"

_ALL_EMAILS = (
    NORMAL_USER_EMAIL, OWNER_A_EMAIL, ADMIN_A_EMAIL, OWNER_B_EMAIL,
)
# platform_admin is intentionally excluded from every delete: once it performs
# a real platform-admin action (login, role change, ...), platform_audit_logs
# rows reference it with ON DELETE RESTRICT and audit rows are immutable
# (insert-only, enforced by a DB trigger) — the row can never be deleted, only
# reused across runs (see _get_or_create_platform_admin).
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _assert_local_test_database() -> None:
    host = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(f"Refusing to run: DATABASE_URL host {host!r} is not local.")
    if settings.is_production:
        raise RuntimeError("Refusing to run: APP_ENV=production.")


async def _cleanup_agency(db, agency_id: uuid.UUID) -> None:
    agency = await db.get(Agency, agency_id)
    if agency is not None:
        await db.delete(agency)


async def cleanup_by_ids(agency_a: uuid.UUID | None, agency_b: uuid.UUID | None) -> None:
    async with AsyncSessionLocal() as db:
        for aid in (agency_a, agency_b):
            if aid is not None:
                await _cleanup_agency(db, aid)
        await db.commit()

        for email in _ALL_EMAILS:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()

        # Plans created by this fixture are identified by their code prefix.
        plans = (await db.execute(
            select(Plan).where(Plan.code.in_(["e2e-white-label", "e2e-starter"]))
        )).scalars().all()
        for plan in plans:
            await db.delete(plan)
        await db.commit()


async def cleanup_by_email() -> None:
    async with AsyncSessionLocal() as db:
        for email in (OWNER_A_EMAIL, OWNER_B_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                continue
            member = (await db.execute(
                select(AgencyMember).where(AgencyMember.user_id == user.id)
            )).scalar_one_or_none()
            if member is not None:
                await _cleanup_agency(db, member.agency_id)
        await db.commit()
    await cleanup_by_ids(None, None)


async def _get_or_create_platform_admin(db) -> User:
    existing = (await db.execute(
        select(User).where(User.email == PLATFORM_ADMIN_EMAIL)
    )).scalar_one_or_none()
    if existing is not None:
        existing.password_hash = hash_password(PASSWORD)
        existing.full_name = "E2E Platform Admin"
        existing.is_active = True
        existing.is_verified = True
        existing.mfa_enabled = False
        existing.mfa_secret_encrypted = None
        # Reset session/MFA-recovery state left over from a previous run so
        # each run starts from a clean, predictable slate.
        await db.execute(delete(UserToken).where(UserToken.user_id == existing.id))
        await db.execute(delete(UserMfaRecoveryCode).where(UserMfaRecoveryCode.user_id == existing.id))
        return existing
    admin = User(
        id=uuid.uuid4(), email=PLATFORM_ADMIN_EMAIL, password_hash=hash_password(PASSWORD),
        full_name="E2E Platform Admin", user_type=UserType.PLATFORM_ADMIN.value,
        is_active=True, is_verified=True,
    )
    db.add(admin)
    return admin


async def _seed_approval_token(db, agency_id: uuid.UUID, requester_id: uuid.UUID, title: str) -> str:
    brief = Brief(
        id=uuid.uuid4(), agency_id=agency_id, title=title, status="ready_for_review",
        created_by_id=requester_id,
    )
    db.add(brief)
    await db.flush()

    version = BriefVersion(
        id=uuid.uuid4(), brief_id=brief.id, version_number=1,
        snapshot={
            "brief": {"title": title, "description": None, "priority": "normal", "deadline": None},
            "brand_name": None,
            "template": None,
            "sections": [],
        },
        created_by_id=requester_id,
    )
    db.add(version)
    await db.flush()

    approval = Approval(
        id=uuid.uuid4(), brief_id=brief.id, version_id=version.id, status="pending",
        channel="public_token", requested_by_id=requester_id,
    )
    db.add(approval)
    await db.flush()

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    db.add(ApprovalToken(
        id=uuid.uuid4(), approval_id=approval.id, token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    ))
    return raw_token


async def seed() -> dict[str, str]:
    async with AsyncSessionLocal() as db:
        platform_admin = await _get_or_create_platform_admin(db)
        normal_user = User(
            id=uuid.uuid4(), email=NORMAL_USER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="E2E Normal User", user_type=UserType.AGENCY_USER.value,
            is_active=True, is_verified=True,
        )
        owner_a = User(
            id=uuid.uuid4(), email=OWNER_A_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="E2E Owner A", user_type=UserType.AGENCY_USER.value,
            is_active=True, is_verified=True,
        )
        admin_a = User(
            id=uuid.uuid4(), email=ADMIN_A_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="E2E Admin A", user_type=UserType.AGENCY_USER.value,
            is_active=True, is_verified=True,
        )
        owner_b = User(
            id=uuid.uuid4(), email=OWNER_B_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="E2E Owner B", user_type=UserType.AGENCY_USER.value,
            is_active=True, is_verified=True,
        )
        db.add_all([platform_admin, normal_user, owner_a, admin_a, owner_b])
        await db.flush()

        plan_wl = Plan(
            id=uuid.uuid4(), code="e2e-white-label", name="E2E White Label Plan",
            monthly_price_cents=9900, yearly_price_cents=99000, white_label_enabled=True,
        )
        plan_starter = Plan(
            id=uuid.uuid4(), code="e2e-starter", name="E2E Starter Plan",
            monthly_price_cents=0, yearly_price_cents=0, white_label_enabled=False,
        )
        db.add_all([plan_wl, plan_starter])
        await db.flush()

        suffix = uuid.uuid4().hex[:8]
        agency_a = Agency(
            id=uuid.uuid4(), name="E2E Beyaz Etiket Ajansı", slug=f"e2e-wl-agency-{suffix}",
            status=AgencyStatus.ACTIVE.value, owner_user_id=owner_a.id, plan_id=plan_wl.id,
        )
        agency_b = Agency(
            id=uuid.uuid4(), name="E2E Varsayılan Ajans", slug=f"e2e-default-agency-{suffix}",
            status=AgencyStatus.ACTIVE.value, owner_user_id=owner_b.id, plan_id=plan_starter.id,
        )
        db.add_all([agency_a, agency_b])
        await db.flush()

        db.add_all([
            Subscription(id=uuid.uuid4(), agency_id=agency_a.id, plan_id=plan_wl.id, status="active"),
            Subscription(id=uuid.uuid4(), agency_id=agency_b.id, plan_id=plan_starter.id, status="active"),
            AgencyMember(
                id=uuid.uuid4(), agency_id=agency_a.id, user_id=owner_a.id,
                role=AgencyMemberRole.OWNER.value, status=AgencyMemberStatus.ACTIVE.value,
            ),
            AgencyMember(
                id=uuid.uuid4(), agency_id=agency_a.id, user_id=admin_a.id,
                role=AgencyMemberRole.ADMIN.value, status=AgencyMemberStatus.ACTIVE.value,
            ),
            AgencyMember(
                id=uuid.uuid4(), agency_id=agency_b.id, user_id=owner_b.id,
                role=AgencyMemberRole.OWNER.value, status=AgencyMemberStatus.ACTIVE.value,
            ),
        ])

        db.add(AgencyBrandingSettings(
            id=uuid.uuid4(), agency_id=agency_a.id,
            brand_name_override="E2E Override Marka",
            primary_color="#E11D48", secondary_color="#FDA4AF", accent_color="#BE123C",
            custom_footer_text="© E2E Override Footer",
            is_white_label_enabled=True,
        ))

        platform_defaults = (await db.execute(
            select(PlatformBrandingDefaults).where(PlatformBrandingDefaults.setting_key == "default")
        )).scalar_one_or_none()
        if platform_defaults is None:
            platform_defaults = PlatformBrandingDefaults(setting_key="default")
            db.add(platform_defaults)
        platform_defaults.portal_name = "E2E Flobrief Platform"
        platform_defaults.primary_color = "#2563EB"
        platform_defaults.accent_color = "#1D4ED8"
        platform_defaults.footer_text = "© E2E Platform Default Footer"

        home_seo = (await db.execute(
            select(PlatformSeoPageSettings).where(PlatformSeoPageSettings.page_key == "home")
        )).scalar_one_or_none()
        if home_seo is None:
            home_seo = PlatformSeoPageSettings(page_key="home")
            db.add(home_seo)
        home_seo.title = "Flobrief — E2E Test Başlığı"
        home_seo.description = "E2E testleri için gerçekçi bir meta açıklama metni, elli karakterin üzerinde."
        home_seo.canonical_url = "https://flobrief.com/"
        home_seo.og_title = "Flobrief E2E"
        home_seo.og_image_url = "https://flobrief.com/og-e2e.png"
        home_seo.indexable = True
        home_seo.follow_links = True

        await db.flush()

        token_a = await _seed_approval_token(db, agency_a.id, owner_a.id, "E2E Approval A")
        token_b = await _seed_approval_token(db, agency_b.id, owner_b.id, "E2E Approval B")

        await db.commit()

        return {
            "agency_a_id": str(agency_a.id),
            "agency_b_id": str(agency_b.id),
            "owner_a_member_id": "",
            "approval_token_a": token_a,
            "approval_token_b": token_b,
        }


async def main() -> None:
    _assert_local_test_database()

    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if mode == "cleanup":
        a = uuid.UUID(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None
        b = uuid.UUID(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None
        await cleanup_by_ids(a, b)
        print("cleaned up")
        return

    await cleanup_by_email()
    ids = await seed()
    print("E2E_PLATFORM_ADMIN_EMAIL=" + PLATFORM_ADMIN_EMAIL)
    print("E2E_NORMAL_USER_EMAIL=" + NORMAL_USER_EMAIL)
    print("E2E_OWNER_A_EMAIL=" + OWNER_A_EMAIL)
    print("E2E_ADMIN_A_EMAIL=" + ADMIN_A_EMAIL)
    print("E2E_OWNER_B_EMAIL=" + OWNER_B_EMAIL)
    print("E2E_PASSWORD=" + PASSWORD)
    print("E2E_APPROVAL_TOKEN_A=" + ids["approval_token_a"])
    print("E2E_APPROVAL_TOKEN_B=" + ids["approval_token_b"])
    print("__AGENCY_A_ID__=" + ids["agency_a_id"])
    print("__AGENCY_B_ID__=" + ids["agency_b_id"])


if __name__ == "__main__":
    asyncio.run(main())

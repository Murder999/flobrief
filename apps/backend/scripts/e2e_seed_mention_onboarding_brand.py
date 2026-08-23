"""E2E fixture for apps/frontend/e2e/mention-flow.spec.ts (brand-portal
mention candidate isolation) and onboarding-flow.spec.ts (brand track).

Creates one Agency with:
  - an owner (drives API calls: brief/deliverable/asset creation, submit,
    assignment)
  - a designer assigned to the brief (must appear as a brand-side mention
    candidate, labelled "Ajans Ekibi")
  - a designer NOT assigned to the brief (must NOT appear as a brand-side
    mention candidate — only assignees + owner/admin are visible to brand
    users, never the whole agency directory)
  - a Brand with a brand_owner and a brand_viewer (both valid mention
    candidates — MentionService does not filter brand members by role)
  - a Brief + one submitted Deliverable + one Asset owned by that brand
  - incomplete brand-track OnboardingProgress for the brand owner

Plus, purely as negative fixtures:
  - a second Brand under the SAME agency with its own brand_owner (proves
    brand-portal candidate isolation between sibling brands)
  - a fully separate second Agency + Brand + brand user (proves isolation
    across tenants)

Two modes:
  python e2e_seed_mention_onboarding_brand.py seed     -> prints E2E_* env vars
  python e2e_seed_mention_onboarding_brand.py cleanup  -> deletes the fixture

Both modes accept an optional --run=<id> flag that suffixes every fixture
email with `+<id>` (e.g. flobrief-e2e-mo-brand-owner+onb-welcome@example.com),
mirroring e2e_seed_mention_onboarding_agency.py — lets independent describe
blocks seed non-colliding instances of this fixture. Omitting --run preserves
the original shared fixture identity used by mention-flow.spec.ts.

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production". API calls target E2E_API_BASE (default
http://127.0.0.1:8003, matching the frontend's E2E_REWRITE_API_PORT
dev-rewrite target — see apps/frontend/.env.local and next.config.mjs).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.agency import Agency  # noqa: E402
from app.models.agency_member import AgencyMember  # noqa: E402
from app.models.brand import Brand  # noqa: E402
from app.models.brand_member import BrandMember  # noqa: E402
from app.models.brief import Brief, BriefAssignee  # noqa: E402
from app.models.enums import (  # noqa: E402
    AgencyMemberRole,
    AgencyMemberStatus,
    AgencyStatus,
    BrandMemberRole,
    BrandMemberStatus,
    BrandStatus,
    UserType,
)
from app.models.user import User  # noqa: E402

BASE_OWNER_EMAIL = "flobrief-e2e-mo-brand-agency-owner@example.com"
BASE_ASSIGNED_DESIGNER_EMAIL = "flobrief-e2e-mo-brand-assigned-designer@example.com"
BASE_UNASSIGNED_DESIGNER_EMAIL = "flobrief-e2e-mo-brand-unassigned-designer@example.com"
BASE_BRAND_OWNER_EMAIL = "flobrief-e2e-mo-brand-owner@example.com"
BASE_BRAND_VIEWER_EMAIL = "flobrief-e2e-mo-brand-viewer@example.com"
BASE_SIBLING_BRAND_OWNER_EMAIL = "flobrief-e2e-mo-sibling-brand-owner@example.com"
BASE_OTHER_TENANT_BRAND_USER_EMAIL = "flobrief-e2e-mo-other-tenant-brand-user@example.com"
PASSWORD = "E2eTest1234!"

API_BASE = os.environ.get("E2E_API_BASE", "http://127.0.0.1:8003")

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _parse_run_id(argv: list[str]) -> str | None:
    for arg in argv:
        if arg.startswith("--run="):
            return arg.split("=", 1)[1] or None
    return None


def _suffixed(base_email: str, run_id: str | None) -> str:
    if not run_id:
        return base_email
    local, domain = base_email.split("@", 1)
    return f"{local}+{run_id}@{domain}"


def _emails_for(run_id: str | None) -> tuple[str, str, str, str, str, str, str]:
    return (
        _suffixed(BASE_OWNER_EMAIL, run_id),
        _suffixed(BASE_ASSIGNED_DESIGNER_EMAIL, run_id),
        _suffixed(BASE_UNASSIGNED_DESIGNER_EMAIL, run_id),
        _suffixed(BASE_BRAND_OWNER_EMAIL, run_id),
        _suffixed(BASE_BRAND_VIEWER_EMAIL, run_id),
        _suffixed(BASE_SIBLING_BRAND_OWNER_EMAIL, run_id),
        _suffixed(BASE_OTHER_TENANT_BRAND_USER_EMAIL, run_id),
    )


def _assert_local_test_database() -> None:
    host = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing to run: DATABASE_URL host {host!r} is not a local host {_LOCAL_HOSTS}. "
            "This script only seeds/cleans up a local test database."
        )
    if settings.is_production:
        raise RuntimeError("Refusing to run: APP_ENV=production.")


def _make_fixture_png(color: tuple[int, int, int], size: tuple[int, int] = (800, 800)) -> bytes:
    import io

    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PNG_ASSET = _make_fixture_png((190, 90, 40))


async def _delete_agency_and_brands(db, agency_id: uuid.UUID) -> None:
    agency = await db.get(Agency, agency_id)
    if agency is not None:
        await db.delete(agency)
    brands = (await db.execute(select(Brand).where(Brand.agency_id == agency_id))).scalars().all()
    for brand in brands:
        await db.delete(brand)


async def cleanup(run_id: str | None = None) -> None:
    all_emails = list(_emails_for(run_id))
    async with AsyncSessionLocal() as db:
        agency_ids: set[uuid.UUID] = set()
        for email in all_emails:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                continue
            member = (
                await db.execute(select(AgencyMember).where(AgencyMember.user_id == user.id))
            ).scalar_one_or_none()
            if member is not None:
                agency_ids.add(member.agency_id)
        for agency_id in agency_ids:
            await _delete_agency_and_brands(db, agency_id)
        await db.commit()

        for email in all_emails:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


async def seed_db(run_id: str | None = None) -> dict[str, uuid.UUID]:
    (
        owner_email,
        assigned_designer_email,
        unassigned_designer_email,
        brand_owner_email,
        brand_viewer_email,
        sibling_brand_owner_email,
        other_tenant_brand_user_email,
    ) = _emails_for(run_id)
    async with AsyncSessionLocal() as db:
        agency = Agency(
            id=uuid.uuid4(),
            name="E2E MO Brand Agency",
            slug=f"e2e-mo-brand-agency-{uuid.uuid4().hex[:8]}",
            status=AgencyStatus.ACTIVE.value,
        )
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name="E2E MO Primary Brand",
            slug=f"e2e-mo-primary-brand-{uuid.uuid4().hex[:8]}",
            status=BrandStatus.ACTIVE.value,
        )
        sibling_brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name="E2E MO Sibling Brand",
            slug=f"e2e-mo-sibling-brand-{uuid.uuid4().hex[:8]}",
            status=BrandStatus.ACTIVE.value,
        )
        other_agency = Agency(
            id=uuid.uuid4(),
            name="E2E MO Brand Other Tenant",
            slug=f"e2e-mo-brand-other-agency-{uuid.uuid4().hex[:8]}",
            status=AgencyStatus.ACTIVE.value,
        )
        other_brand = Brand(
            id=uuid.uuid4(),
            agency_id=other_agency.id,
            name="E2E MO Other Tenant Brand",
            slug=f"e2e-mo-other-tenant-brand-{uuid.uuid4().hex[:8]}",
            status=BrandStatus.ACTIVE.value,
        )
        db.add_all([agency, brand, sibling_brand, other_agency, other_brand])

        owner_user = User(
            id=uuid.uuid4(),
            email=owner_email,
            password_hash=hash_password(PASSWORD),
            full_name="E2E MO Brand Agency Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        assigned_designer = User(
            id=uuid.uuid4(),
            email=assigned_designer_email,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Assigned Designer",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        unassigned_designer = User(
            id=uuid.uuid4(),
            email=unassigned_designer_email,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Unassigned Designer",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        brand_owner_user = User(
            id=uuid.uuid4(),
            email=brand_owner_email,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Brand Owner",
            user_type=UserType.BRAND_USER.value,
            is_active=True,
            is_verified=True,
        )
        brand_viewer_user = User(
            id=uuid.uuid4(),
            email=brand_viewer_email,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Brand Viewer",
            user_type=UserType.BRAND_USER.value,
            is_active=True,
            is_verified=True,
        )
        sibling_brand_owner = User(
            id=uuid.uuid4(),
            email=sibling_brand_owner_email,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Sibling Brand Owner",
            user_type=UserType.BRAND_USER.value,
            is_active=True,
            is_verified=True,
        )
        other_tenant_brand_user = User(
            id=uuid.uuid4(),
            email=other_tenant_brand_user_email,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Other Tenant Brand User",
            user_type=UserType.BRAND_USER.value,
            is_active=True,
            is_verified=True,
        )
        db.add_all(
            [
                owner_user,
                assigned_designer,
                unassigned_designer,
                brand_owner_user,
                brand_viewer_user,
                sibling_brand_owner,
                other_tenant_brand_user,
            ]
        )
        await db.flush()

        db.add_all(
            [
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=owner_user.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=assigned_designer.id,
                    role=AgencyMemberRole.DESIGNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=unassigned_designer.id,
                    role=AgencyMemberRole.DESIGNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                BrandMember(
                    id=uuid.uuid4(),
                    brand_id=brand.id,
                    user_id=brand_owner_user.id,
                    role=BrandMemberRole.BRAND_OWNER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                ),
                BrandMember(
                    id=uuid.uuid4(),
                    brand_id=brand.id,
                    user_id=brand_viewer_user.id,
                    role=BrandMemberRole.BRAND_VIEWER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                ),
                BrandMember(
                    id=uuid.uuid4(),
                    brand_id=sibling_brand.id,
                    user_id=sibling_brand_owner.id,
                    role=BrandMemberRole.BRAND_OWNER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                ),
                BrandMember(
                    id=uuid.uuid4(),
                    brand_id=other_brand.id,
                    user_id=other_tenant_brand_user.id,
                    role=BrandMemberRole.BRAND_OWNER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                ),
            ]
        )

        brief = Brief(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand.id,
            title="E2E MO Brand Brief",
            status="in_production",
            created_by_id=owner_user.id,
        )
        db.add(brief)
        await db.flush()

        db.add(
            BriefAssignee(
                id=uuid.uuid4(),
                brief_id=brief.id,
                user_id=assigned_designer.id,
                participant_role="designer",
            )
        )
        await db.commit()

        return {
            "agency_id": agency.id,
            "brand_id": brand.id,
            "sibling_brand_id": sibling_brand.id,
            "other_agency_id": other_agency.id,
            "other_brand_id": other_brand.id,
            "brief_id": brief.id,
            "owner_user_id": owner_user.id,
            "assigned_designer_id": assigned_designer.id,
            "unassigned_designer_id": unassigned_designer.id,
            "brand_owner_user_id": brand_owner_user.id,
            "brand_viewer_user_id": brand_viewer_user.id,
        }


async def seed_content(
    ids: dict[str, uuid.UUID], dismiss_onboarding: bool = True
) -> dict[str, str]:
    token = create_access_token(str(ids["owner_user_id"]))
    headers = {"Authorization": f"Bearer {token}", "X-Agency-ID": str(ids["agency_id"])}
    brief_id = ids["brief_id"]

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables",
            json={"title": "E2E MO Brand Deliverable", "deliverable_type": "image"},
            headers=headers,
        )
        resp.raise_for_status()
        deliverable_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/assets",
            headers=headers,
            files={"file": ("e2e-mo-brand-asset.png", PNG_ASSET, "image/png")},
        )
        resp.raise_for_status()
        asset_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/submit",
            headers=headers,
        )
        resp.raise_for_status()

        # Instantiate brand OnboardingProgress, then dismiss it via the real
        # dismiss endpoint (not a raw DB write) so mention-flow.spec.ts's brand
        # owner login never races the welcome-modal overlay — that spec tests
        # mention candidate isolation, not onboarding.
        brand_owner_token = create_access_token(str(ids["brand_owner_user_id"]))
        brand_owner_headers = {"Authorization": f"Bearer {brand_owner_token}"}
        progress = await client.get(
            "/api/v1/brand-portal/onboarding/progress", headers=brand_owner_headers
        )
        progress.raise_for_status()
        if dismiss_onboarding:
            dismiss_resp = await client.post(
                "/api/v1/brand-portal/onboarding/progress/dismiss", headers=brand_owner_headers
            )
            dismiss_resp.raise_for_status()

        return {"deliverable_id": deliverable_id, "asset_id": asset_id}


async def main() -> None:
    _assert_local_test_database()

    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    run_id = _parse_run_id(sys.argv[2:])
    if mode == "cleanup":
        await cleanup(run_id)
        print("cleaned up")
        return

    dismiss_onboarding = "no-dismiss" not in sys.argv[2:]

    (
        owner_email,
        assigned_designer_email,
        unassigned_designer_email,
        brand_owner_email,
        brand_viewer_email,
        sibling_brand_owner_email,
        other_tenant_brand_user_email,
    ) = _emails_for(run_id)

    await cleanup(run_id)
    ids = await seed_db(run_id)
    content_ids = await seed_content(ids, dismiss_onboarding=dismiss_onboarding)

    print("E2E_AGENCY_ID=" + str(ids["agency_id"]))
    print("E2E_BRAND_ID=" + str(ids["brand_id"]))
    print("E2E_SIBLING_BRAND_ID=" + str(ids["sibling_brand_id"]))
    print("E2E_OTHER_AGENCY_ID=" + str(ids["other_agency_id"]))
    print("E2E_OTHER_BRAND_ID=" + str(ids["other_brand_id"]))
    print("E2E_BRIEF_ID=" + str(ids["brief_id"]))
    print("E2E_OWNER_EMAIL=" + owner_email)
    print("E2E_ASSIGNED_DESIGNER_EMAIL=" + assigned_designer_email)
    print("E2E_UNASSIGNED_DESIGNER_EMAIL=" + unassigned_designer_email)
    print("E2E_BRAND_OWNER_EMAIL=" + brand_owner_email)
    print("E2E_BRAND_VIEWER_EMAIL=" + brand_viewer_email)
    print("E2E_SIBLING_BRAND_OWNER_EMAIL=" + sibling_brand_owner_email)
    print("E2E_OTHER_TENANT_BRAND_USER_EMAIL=" + other_tenant_brand_user_email)
    print("E2E_PASSWORD=" + PASSWORD)
    print("E2E_DELIVERABLE_ID=" + content_ids["deliverable_id"])
    print("E2E_ASSET_ID=" + content_ids["asset_id"])


if __name__ == "__main__":
    asyncio.run(main())

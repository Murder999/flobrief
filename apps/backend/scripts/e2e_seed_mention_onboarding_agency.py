"""E2E fixture for apps/frontend/e2e/mention-flow.spec.ts and
onboarding-flow.spec.ts (agency side).

Creates one Agency with:
  - an owner (agency_owner_admin onboarding track)
  - a designer (agency_member onboarding track; a valid agency-side mention
    candidate; Turkish-charactered, moderately long display name for
    search/rendering stress coverage)
  - a viewer (must never appear as a mention candidate — MentionService
    excludes the viewer role from agency candidates)
  - a Brand, a Brief, two independent Deliverables, one uploaded Asset
  - a comment thread with an initial comment mentioning the designer
  - an annotation on the submitted deliverable mentioning the designer
  - incomplete OnboardingProgress rows for both the owner and the designer

Plus a fully separate second Agency (owner-only) used purely as the
"another tenant" negative fixture for cross-tenant candidate/isolation
checks — never touched by any positive-path scenario.

Two modes:
  python e2e_seed_mention_onboarding_agency.py seed     -> prints E2E_* env vars
  python e2e_seed_mention_onboarding_agency.py cleanup  -> deletes the fixture

Both modes accept an optional --run=<id> flag that suffixes every fixture
email with `+<id>` (e.g. flobrief-e2e-mo-agency-owner+onb-welcome@example.com).
This lets multiple independent describe blocks in the same spec file (or
multiple spec files) seed non-colliding instances of this fixture concurrently
or in isolation from one another — each seed call still self-cleans (any
prior fixture under the same --run id) before creating, and cleanup targets
exactly the emails for that id. Omitting --run preserves the original shared
fixture identity used by mention-flow.spec.ts.

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production" — mirrors e2e_seed_preview_center.py. API calls
target E2E_API_BASE (default http://127.0.0.1:8003, matching the frontend's
E2E_REWRITE_API_PORT dev-rewrite target — see apps/frontend/.env.local and
next.config.mjs) so this script talks to the same backend instance
Playwright's browser actually exercises, instead of an unrelated port 8000.
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
from app.models.brief import Brief  # noqa: E402
from app.models.enums import (  # noqa: E402
    AgencyMemberRole,
    AgencyMemberStatus,
    AgencyStatus,
    BrandStatus,
    UserType,
)
from app.models.user import User  # noqa: E402

BASE_OWNER_EMAIL = "flobrief-e2e-mo-agency-owner@example.com"
BASE_DESIGNER_EMAIL = "flobrief-e2e-mo-agency-designer@example.com"
BASE_VIEWER_EMAIL = "flobrief-e2e-mo-agency-viewer@example.com"
BASE_OTHER_TENANT_OWNER_EMAIL = "flobrief-e2e-mo-agency-other-tenant@example.com"
PASSWORD = "E2eTest1234!"

DESIGNER_FULL_NAME = "Ayşe Öztürk Yılmazoğlu"  # Turkish chars + longer name, deliberately

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


def _emails_for(run_id: str | None) -> tuple[str, str, str, str]:
    return (
        _suffixed(BASE_OWNER_EMAIL, run_id),
        _suffixed(BASE_DESIGNER_EMAIL, run_id),
        _suffixed(BASE_VIEWER_EMAIL, run_id),
        _suffixed(BASE_OTHER_TENANT_OWNER_EMAIL, run_id),
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


PNG_ASSET = _make_fixture_png((60, 130, 200))


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
    owner_email, designer_email, viewer_email, other_tenant_owner_email = _emails_for(run_id)
    async with AsyncSessionLocal() as db:
        agency = Agency(
            id=uuid.uuid4(),
            name="E2E Mention/Onboarding Agency",
            slug=f"e2e-mo-agency-{uuid.uuid4().hex[:8]}",
            status=AgencyStatus.ACTIVE.value,
        )
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name="E2E Mention/Onboarding Brand",
            slug=f"e2e-mo-brand-{uuid.uuid4().hex[:8]}",
            status=BrandStatus.ACTIVE.value,
        )
        other_agency = Agency(
            id=uuid.uuid4(),
            name="E2E Mention/Onboarding Other Tenant",
            slug=f"e2e-mo-other-agency-{uuid.uuid4().hex[:8]}",
            status=AgencyStatus.ACTIVE.value,
        )
        db.add_all([agency, brand, other_agency])

        owner_user = User(
            id=uuid.uuid4(),
            email=owner_email,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Agency Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        designer_user = User(
            id=uuid.uuid4(),
            email=designer_email,
            password_hash=hash_password(PASSWORD),
            full_name=DESIGNER_FULL_NAME,
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        viewer_user = User(
            id=uuid.uuid4(),
            email=viewer_email,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Agency Viewer",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        other_tenant_owner = User(
            id=uuid.uuid4(),
            email=other_tenant_owner_email,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Other Tenant Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        db.add_all([owner_user, designer_user, viewer_user, other_tenant_owner])
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
                    user_id=designer_user.id,
                    role=AgencyMemberRole.DESIGNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=viewer_user.id,
                    role=AgencyMemberRole.VIEWER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=other_agency.id,
                    user_id=other_tenant_owner.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
            ]
        )

        brief = Brief(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand.id,
            title="E2E Mention/Onboarding Brief",
            status="in_production",
            created_by_id=owner_user.id,
        )
        db.add(brief)
        await db.commit()

        return {
            "agency_id": agency.id,
            "other_agency_id": other_agency.id,
            "brand_id": brand.id,
            "brief_id": brief.id,
            "owner_user_id": owner_user.id,
            "designer_user_id": designer_user.id,
            "viewer_user_id": viewer_user.id,
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
            json={"title": "E2E MO Deliverable One", "deliverable_type": "image"},
            headers=headers,
        )
        resp.raise_for_status()
        deliverable_1_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables",
            json={"title": "E2E MO Deliverable Two", "deliverable_type": "image"},
            headers=headers,
        )
        resp.raise_for_status()
        deliverable_2_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_1_id}/assets",
            headers=headers,
            files={"file": ("e2e-mo-asset.png", PNG_ASSET, "image/png")},
        )
        resp.raise_for_status()
        asset_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_1_id}/submit",
            headers=headers,
        )
        resp.raise_for_status()

        first_name = DESIGNER_FULL_NAME.split(" ")[0]
        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/threads",
            headers=headers,
            json={
                "thread_type": "brief",
                "initial_comment": f"Merhaba @{first_name}, bakabilir misin?",
                "visibility": "internal",
                "mentioned_user_ids": [str(ids["designer_user_id"])],
            },
        )
        resp.raise_for_status()
        thread_id = resp.json()["id"]
        comment_id = resp.json()["comments"][0]["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_1_id}/annotations",
            headers=headers,
            json={
                "asset_id": asset_id,
                "version_number": 1,
                "x_percent": 40.0,
                "y_percent": 35.0,
                "annotation_type": "revision",
                "visibility": "client_visible",
                "body": f"@{first_name} bu alanı gözden geçirir misin?",
                "mentioned_user_ids": [str(ids["designer_user_id"])],
            },
        )
        resp.raise_for_status()
        annotation_id = resp.json()["id"]

        # Instantiate OnboardingProgress for owner + designer, then dismiss it
        # via the real dismiss endpoint (not a raw DB write) so a fresh mention
        # test run never races the welcome-modal overlay in OnboardingWizard —
        # mention-flow.spec.ts tests mentions, not onboarding, so its actors
        # start in a realistic "already dismissed the tour" state.
        # onboarding-flow.spec.ts reuses this same fixture but tests the
        # opposite: the fresh, undismissed welcome-modal experience — it
        # passes dismiss_onboarding=False to skip this step and get a real
        # "never seen onboarding" user/designer instead.
        owner_progress = await client.get("/api/v1/onboarding/progress", headers=headers)
        owner_progress.raise_for_status()
        if dismiss_onboarding:
            dismiss_owner = await client.post(
                "/api/v1/onboarding/progress/dismiss", headers=headers
            )
            dismiss_owner.raise_for_status()

        designer_token = create_access_token(str(ids["designer_user_id"]))
        designer_headers = {
            "Authorization": f"Bearer {designer_token}",
            "X-Agency-ID": str(ids["agency_id"]),
        }
        designer_progress = await client.get(
            "/api/v1/onboarding/progress", headers=designer_headers
        )
        designer_progress.raise_for_status()
        if dismiss_onboarding:
            dismiss_designer = await client.post(
                "/api/v1/onboarding/progress/dismiss", headers=designer_headers
            )
            dismiss_designer.raise_for_status()

        return {
            "deliverable_1_id": deliverable_1_id,
            "deliverable_2_id": deliverable_2_id,
            "asset_id": asset_id,
            "thread_id": thread_id,
            "comment_id": comment_id,
            "annotation_id": annotation_id,
        }


async def main() -> None:
    _assert_local_test_database()

    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    run_id = _parse_run_id(sys.argv[2:])
    if mode == "cleanup":
        await cleanup(run_id)
        print("cleaned up")
        return

    dismiss_onboarding = "no-dismiss" not in sys.argv[2:]

    owner_email, designer_email, viewer_email, other_tenant_owner_email = _emails_for(run_id)
    await cleanup(run_id)
    ids = await seed_db(run_id)
    content_ids = await seed_content(ids, dismiss_onboarding=dismiss_onboarding)

    print("E2E_AGENCY_ID=" + str(ids["agency_id"]))
    print("E2E_OTHER_AGENCY_ID=" + str(ids["other_agency_id"]))
    print("E2E_BRAND_ID=" + str(ids["brand_id"]))
    print("E2E_BRIEF_ID=" + str(ids["brief_id"]))
    print("E2E_OWNER_EMAIL=" + owner_email)
    print("E2E_DESIGNER_EMAIL=" + designer_email)
    print("E2E_DESIGNER_FULL_NAME=" + DESIGNER_FULL_NAME)
    print("E2E_VIEWER_EMAIL=" + viewer_email)
    print("E2E_OTHER_TENANT_OWNER_EMAIL=" + other_tenant_owner_email)
    print("E2E_PASSWORD=" + PASSWORD)
    print("E2E_DELIVERABLE_1_ID=" + content_ids["deliverable_1_id"])
    print("E2E_DELIVERABLE_2_ID=" + content_ids["deliverable_2_id"])
    print("E2E_ASSET_ID=" + content_ids["asset_id"])
    print("E2E_THREAD_ID=" + content_ids["thread_id"])
    print("E2E_COMMENT_ID=" + content_ids["comment_id"])
    print("E2E_ANNOTATION_ID=" + content_ids["annotation_id"])


if __name__ == "__main__":
    asyncio.run(main())

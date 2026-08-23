"""E2E fixture for e2e/preview-center-flow.spec.ts (Social Media Preview Center).

Creates one Agency + agency owner User, one Brand + brand owner User, a Brief,
and ONE DRAFT Deliverable with two real uploaded image assets (so the
carousel-format platform preview + carousel reorder editor has two real
slides to work with, and the deliverable is still editable when the spec
starts — the agency configures/edits the preview, then submits it via the
UI's own "Onaya Gönder" button so the brand-side portion of the spec can view
the exact same, real submitted deliverable).

Two modes:
  python e2e_seed_preview_center.py seed      -> prints E2E_* env vars
  python e2e_seed_preview_center.py cleanup <agency_id>  -> deletes the fixture

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production" — mirrors e2e_seed_brief_workspace.py.
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
from app.models.brief import Brief  # noqa: E402
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

AGENCY_EMAIL = "flobrief-e2e-preview-agency@example.com"
BRAND_EMAIL = "flobrief-e2e-preview-brand@example.com"
PASSWORD = "E2eTest1234!"
API_BASE = os.environ.get("E2E_API_BASE", "http://127.0.0.1:8003")

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _assert_local_test_database() -> None:
    host = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing to run: DATABASE_URL host {host!r} is not a local host {_LOCAL_HOSTS}. "
            "This script only seeds/cleans up a local test database."
        )
    if settings.is_production:
        raise RuntimeError("Refusing to run: APP_ENV=production.")


def _make_fixture_png(color: tuple[int, int, int], size: tuple[int, int] = (1080, 1080)) -> bytes:
    import io

    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PNG_SLIDE_1 = _make_fixture_png((40, 110, 190))
PNG_SLIDE_2 = _make_fixture_png((190, 90, 40))


async def cleanup_by_email() -> None:
    async with AsyncSessionLocal() as db:
        for email in (AGENCY_EMAIL, BRAND_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                continue
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

        for email in (AGENCY_EMAIL, BRAND_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


async def cleanup_by_agency_id(agency_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        agency = await db.get(Agency, agency_id)
        if agency is not None:
            await db.delete(agency)
        brands = (
            (await db.execute(select(Brand).where(Brand.agency_id == agency_id))).scalars().all()
        )
        for brand in brands:
            await db.delete(brand)
        await db.commit()

        for email in (AGENCY_EMAIL, BRAND_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


async def seed_db() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as db:
        agency = Agency(
            id=uuid.uuid4(),
            name="E2E Preview Agency",
            slug=f"e2e-preview-agency-{uuid.uuid4().hex[:8]}",
            status=AgencyStatus.ACTIVE.value,
        )
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name="E2E Preview Brand",
            slug=f"e2e-preview-brand-{uuid.uuid4().hex[:8]}",
            status=BrandStatus.ACTIVE.value,
        )
        db.add_all([agency, brand])

        agency_user = User(
            id=uuid.uuid4(),
            email=AGENCY_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Preview Agency Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        brand_user = User(
            id=uuid.uuid4(),
            email=BRAND_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Preview Brand Owner",
            user_type=UserType.BRAND_USER.value,
            is_active=True,
            is_verified=True,
        )
        db.add_all([agency_user, brand_user])
        await db.flush()

        db.add_all(
            [
                AgencyMember(
                    id=uuid.uuid4(),
                    agency_id=agency.id,
                    user_id=agency_user.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                BrandMember(
                    id=uuid.uuid4(),
                    brand_id=brand.id,
                    user_id=brand_user.id,
                    role=BrandMemberRole.BRAND_OWNER.value,
                    status=BrandMemberStatus.ACTIVE.value,
                ),
            ]
        )

        brief = Brief(
            id=uuid.uuid4(),
            agency_id=agency.id,
            brand_id=brand.id,
            title="E2E Preview Center Brief",
            status="in_production",
            created_by_id=agency_user.id,
        )
        db.add(brief)
        await db.commit()

        return agency.id, brand.id, brief.id, agency_user.id, brand_user.id


async def dismiss_onboarding(
    agency_id: uuid.UUID, agency_user_id: uuid.UUID, brand_user_id: uuid.UUID
) -> None:
    """Seeds both fixture users' onboarding as already dismissed via the real
    dismiss endpoints (not a raw DB write) — this spec exercises the Preview
    Center, not onboarding, so its actors must start in a realistic
    "already dismissed the tour" state instead of racing the welcome-modal
    overlay in OnboardingWizard.tsx (mirrors e2e_seed_mention_onboarding_*.py)."""
    agency_token = create_access_token(str(agency_user_id))
    agency_headers = {"Authorization": f"Bearer {agency_token}", "X-Agency-ID": str(agency_id)}
    brand_token = create_access_token(str(brand_user_id))
    brand_headers = {"Authorization": f"Bearer {brand_token}"}

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        agency_progress = await client.get("/api/v1/onboarding/progress", headers=agency_headers)
        agency_progress.raise_for_status()
        agency_dismiss = await client.post(
            "/api/v1/onboarding/progress/dismiss", headers=agency_headers
        )
        agency_dismiss.raise_for_status()

        brand_progress = await client.get(
            "/api/v1/brand-portal/onboarding/progress", headers=brand_headers
        )
        brand_progress.raise_for_status()
        brand_dismiss = await client.post(
            "/api/v1/brand-portal/onboarding/progress/dismiss", headers=brand_headers
        )
        brand_dismiss.raise_for_status()


async def seed_draft_deliverable(
    agency_id: uuid.UUID, brief_id: uuid.UUID, agency_user_id: uuid.UUID
) -> dict[str, str]:
    token = create_access_token(str(agency_user_id))
    headers = {"Authorization": f"Bearer {token}", "X-Agency-ID": str(agency_id)}

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables",
            json={"title": "E2E Preview Deliverable", "deliverable_type": "image"},
            headers=headers,
        )
        resp.raise_for_status()
        deliverable_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/assets",
            headers=headers,
            files={"file": ("e2e-preview-slide-1.png", PNG_SLIDE_1, "image/png")},
        )
        resp.raise_for_status()
        asset_1_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/assets",
            headers=headers,
            files={"file": ("e2e-preview-slide-2.png", PNG_SLIDE_2, "image/png")},
        )
        resp.raise_for_status()
        asset_2_id = resp.json()["id"]

        return {
            "deliverable_id": deliverable_id,
            "asset_1_id": asset_1_id,
            "asset_2_id": asset_2_id,
        }


async def seed_version_chain_deliverables(
    agency_id: uuid.UUID, brief_id: uuid.UUID, agency_user_id: uuid.UUID
) -> dict[str, str]:
    """Two independent deliverables (distinct titles) plus a same-title pair
    representing a resubmission — fixture for the is_latest_version
    regression coverage (see app/services/deliverable_versioning.py)."""
    token = create_access_token(str(agency_user_id))
    headers = {"Authorization": f"Bearer {token}", "X-Agency-ID": str(agency_id)}

    async def create_and_submit(client: httpx.AsyncClient, title: str) -> str:
        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables",
            json={"title": title, "deliverable_type": "image"},
            headers=headers,
        )
        resp.raise_for_status()
        deliverable_id = resp.json()["id"]
        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/assets",
            headers=headers,
            files={"file": ("e2e-version-chain.png", PNG_SLIDE_1, "image/png")},
        )
        resp.raise_for_status()
        # Preview config can only be written while the deliverable is still
        # draft — must happen before submit (see _require_editable).
        resp = await client.put(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=headers,
            json={"platform": "instagram", "preview_format": "feed_single"},
        )
        resp.raise_for_status()
        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/submit",
            headers=headers,
        )
        resp.raise_for_status()
        return deliverable_id

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        independent_a = await create_and_submit(client, "E2E Independent Instagram Post")
        independent_b = await create_and_submit(client, "E2E Independent LinkedIn Görsel")
        old_version = await create_and_submit(client, "E2E Version Chain Görseli")
        new_version = await create_and_submit(client, "E2E Version Chain Görseli")

        return {
            "independent_a_id": independent_a,
            "independent_b_id": independent_b,
            "old_version_id": old_version,
            "new_version_id": new_version,
        }


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
    agency_id, brand_id, brief_id, agency_user_id, brand_user_id = await seed_db()
    await dismiss_onboarding(agency_id, agency_user_id, brand_user_id)
    ids = await seed_draft_deliverable(agency_id, brief_id, agency_user_id)
    chain_ids = await seed_version_chain_deliverables(agency_id, brief_id, agency_user_id)
    print("E2E_AGENCY_EMAIL=" + AGENCY_EMAIL)
    print("E2E_BRAND_EMAIL=" + BRAND_EMAIL)
    print("E2E_PASSWORD=" + PASSWORD)
    print("E2E_BRIEF_ID=" + str(brief_id))
    print("E2E_BRAND_ID=" + str(brand_id))
    print("E2E_DELIVERABLE_ID=" + ids["deliverable_id"])
    print("E2E_ASSET_1_ID=" + ids["asset_1_id"])
    print("E2E_ASSET_2_ID=" + ids["asset_2_id"])
    print("E2E_INDEPENDENT_A_ID=" + chain_ids["independent_a_id"])
    print("E2E_INDEPENDENT_B_ID=" + chain_ids["independent_b_id"])
    print("E2E_OLD_VERSION_ID=" + chain_ids["old_version_id"])
    print("E2E_NEW_VERSION_ID=" + chain_ids["new_version_id"])
    print("__AGENCY_ID__=" + str(agency_id))


if __name__ == "__main__":
    asyncio.run(main())

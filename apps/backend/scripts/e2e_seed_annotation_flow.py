"""E2E fixture for apps/frontend/e2e/annotation-flow.spec.ts.

Creates one Agency + agency owner User, one Brand + brand owner User, a
Brief, and one submitted image Deliverable titled "E2E Görsel" (the exact
title the spec asserts on), driving the *actual* deliverables API (asset
upload + submit) against a running backend so the uploaded image is
servable through the real download endpoint — not hand-inserted rows that
would bypass storage_service.

Replaces the previous ad-hoc, gitignored `_tmp_annotation_e2e_seed.py` —
this script is tracked, repeatable (cleanup-then-seed under fixed emails,
mirrors e2e_seed_preview_center.py / e2e_seed_mention_onboarding_agency.py),
self-cleaning (`cleanup` mode), and independent of any other spec's fixture
state.

Two modes:
  python e2e_seed_annotation_flow.py seed     -> prints E2E_* env vars
  python e2e_seed_annotation_flow.py cleanup  -> deletes the fixture

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production" — mirrors the other tracked e2e_seed_*.py
scripts.
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

AGENCY_EMAIL = "flobrief-e2e-annotation-agency@example.com"
BRAND_EMAIL = "flobrief-e2e-annotation-brand@example.com"
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


# A real 800x450 (16:9) image, not a degenerate 1x1 pixel — a square source
# image renders (via w-full h-full object-contain, with no fixed container
# height) at container-width-square, which is taller than the viewport and
# pushes the container's vertical center below the fold, causing the E2E
# canvas click to land outside the actual clickable area.
def _make_fixture_png() -> bytes:
    import io

    img = Image.new("RGB", (800, 450), color=(200, 60, 60))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PNG_BYTES = _make_fixture_png()


async def cleanup() -> None:
    async with AsyncSessionLocal() as db:
        for email in (AGENCY_EMAIL, BRAND_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                continue
            member = (await db.execute(
                select(AgencyMember).where(AgencyMember.user_id == user.id)
            )).scalar_one_or_none()
            if member is not None:
                agency = await db.get(Agency, member.agency_id)
                if agency is not None:
                    await db.delete(agency)  # cascades agency_members/briefs/deliverables/...
                brands = (await db.execute(
                    select(Brand).where(Brand.agency_id == member.agency_id)
                )).scalars().all()
                for brand in brands:
                    await db.delete(brand)  # cascades brand_members
        await db.commit()

        for email in (AGENCY_EMAIL, BRAND_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


async def seed_db() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as db:
        agency = Agency(
            id=uuid.uuid4(), name="E2E Annotation Agency",
            slug=f"e2e-annotation-agency-{uuid.uuid4().hex[:8]}", status=AgencyStatus.ACTIVE.value,
        )
        brand = Brand(
            id=uuid.uuid4(), agency_id=agency.id, name="E2E Annotation Brand",
            slug=f"e2e-annotation-brand-{uuid.uuid4().hex[:8]}", status=BrandStatus.ACTIVE.value,
        )
        db.add_all([agency, brand])

        agency_user = User(
            id=uuid.uuid4(), email=AGENCY_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="E2E Annotation Agency Owner", user_type=UserType.AGENCY_USER.value,
            is_active=True, is_verified=True,
        )
        brand_user = User(
            id=uuid.uuid4(), email=BRAND_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="E2E Annotation Brand Owner", user_type=UserType.BRAND_USER.value,
            is_active=True, is_verified=True,
        )
        db.add_all([agency_user, brand_user])
        await db.flush()

        db.add_all([
            AgencyMember(
                id=uuid.uuid4(), agency_id=agency.id, user_id=agency_user.id,
                role=AgencyMemberRole.OWNER.value, status=AgencyMemberStatus.ACTIVE.value,
            ),
            BrandMember(
                id=uuid.uuid4(), brand_id=brand.id, user_id=brand_user.id,
                role=BrandMemberRole.BRAND_OWNER.value, status=BrandMemberStatus.ACTIVE.value,
            ),
        ])

        brief = Brief(
            id=uuid.uuid4(), agency_id=agency.id, brand_id=brand.id,
            title="E2E Annotation Brief", status="in_production",
            created_by_id=agency_user.id,
        )
        db.add(brief)
        await db.commit()

        return agency.id, brief.id, agency_user.id, brand_user.id


async def seed_deliverable_via_api(
    agency_id: uuid.UUID, brief_id: uuid.UUID, agency_user_id: uuid.UUID, brand_user_id: uuid.UUID
) -> None:
    token = create_access_token(str(agency_user_id))
    headers = {"Authorization": f"Bearer {token}", "X-Agency-ID": str(agency_id)}

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables",
            json={"title": "E2E Görsel", "deliverable_type": "image"},
            headers=headers,
        )
        resp.raise_for_status()
        deliverable_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/assets",
            headers=headers,
            files={"file": ("e2e-annotation-fixture.png", PNG_BYTES, "image/png")},
        )
        resp.raise_for_status()

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/submit",
            headers=headers,
        )
        resp.raise_for_status()

        # Instantiate + dismiss OnboardingProgress via the real dismiss
        # endpoint (not a raw DB write) for both actors, so the spec never
        # races the welcome-modal overlay (OnboardingWizard.tsx) — mirrors
        # e2e_seed_mention_onboarding_agency.py/_brand.py's same fixture.
        agency_progress = await client.get("/api/v1/onboarding/progress", headers=headers)
        agency_progress.raise_for_status()
        dismiss_agency = await client.post(
            "/api/v1/onboarding/progress/dismiss", headers=headers
        )
        dismiss_agency.raise_for_status()

        brand_token = create_access_token(str(brand_user_id))
        brand_headers = {"Authorization": f"Bearer {brand_token}"}
        brand_progress = await client.get(
            "/api/v1/brand-portal/onboarding/progress", headers=brand_headers
        )
        brand_progress.raise_for_status()
        dismiss_brand = await client.post(
            "/api/v1/brand-portal/onboarding/progress/dismiss", headers=brand_headers
        )
        dismiss_brand.raise_for_status()


async def main() -> None:
    _assert_local_test_database()

    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if mode == "cleanup":
        await cleanup()
        print("cleaned up")
        return

    await cleanup()
    agency_id, brief_id, agency_user_id, brand_user_id = await seed_db()
    await seed_deliverable_via_api(agency_id, brief_id, agency_user_id, brand_user_id)
    print("E2E_AGENCY_EMAIL=" + AGENCY_EMAIL)
    print("E2E_BRAND_EMAIL=" + BRAND_EMAIL)
    print("E2E_PASSWORD=" + PASSWORD)
    print("E2E_BRIEF_ID=" + str(brief_id))
    print("__AGENCY_ID__=" + str(agency_id))


if __name__ == "__main__":
    asyncio.run(main())

"""E2E fixture for e2e/deliverable-create-flow.spec.ts.

Regression coverage for the "add a second independent deliverable" gap: a
brief with at least one existing deliverable had no visible UI action to
create a second one (NewDeliverableForm was defined but never mounted).

Creates one Agency with two members (OWNER — can create; VIEWER — cannot),
one Brand + brand owner User, a Brief with ONE existing draft image
deliverable already on it (so the spec starts from the "at least one
deliverable already exists" state the bug required).

Two modes:
  python e2e_seed_deliverable_create.py seed      -> prints E2E_* env vars
  python e2e_seed_deliverable_create.py cleanup <agency_id>  -> deletes the fixture

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production" — mirrors e2e_seed_preview_center.py.
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

OWNER_EMAIL = "flobrief-e2e-delcreate-owner@example.com"
VIEWER_EMAIL = "flobrief-e2e-delcreate-viewer@example.com"
BRAND_EMAIL = "flobrief-e2e-delcreate-brand@example.com"
PASSWORD = "E2eTest1234!"
API_BASE = os.environ.get("E2E_API_BASE", "http://127.0.0.1:8003")

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_ALL_EMAILS = (OWNER_EMAIL, VIEWER_EMAIL, BRAND_EMAIL)


def _make_fixture_png(color: tuple[int, int, int] = (40, 110, 190)) -> bytes:
    import io

    img = Image.new("RGB", (600, 600), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _assert_local_test_database() -> None:
    host = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing to run: DATABASE_URL host {host!r} is not a local host {_LOCAL_HOSTS}. "
            "This script only seeds/cleans up a local test database."
        )
    if settings.is_production:
        raise RuntimeError("Refusing to run: APP_ENV=production.")


async def _delete_users_by_email() -> None:
    async with AsyncSessionLocal() as db:
        for email in _ALL_EMAILS:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is not None:
                await db.delete(user)
        await db.commit()


async def cleanup_by_email() -> None:
    async with AsyncSessionLocal() as db:
        for email in _ALL_EMAILS:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                continue
            member = (await db.execute(
                select(AgencyMember).where(AgencyMember.user_id == user.id)
            )).scalar_one_or_none()
            if member is not None:
                agency = await db.get(Agency, member.agency_id)
                if agency is not None:
                    await db.delete(agency)
                brands = (await db.execute(
                    select(Brand).where(Brand.agency_id == member.agency_id)
                )).scalars().all()
                for brand in brands:
                    await db.delete(brand)
        await db.commit()
    await _delete_users_by_email()


async def cleanup_by_agency_id(agency_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        agency = await db.get(Agency, agency_id)
        if agency is not None:
            await db.delete(agency)
        brands = (await db.execute(
            select(Brand).where(Brand.agency_id == agency_id)
        )).scalars().all()
        for brand in brands:
            await db.delete(brand)
        await db.commit()
    await _delete_users_by_email()


async def seed_db() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as db:
        agency = Agency(
            id=uuid.uuid4(), name="E2E Deliverable Create Agency",
            slug=f"e2e-delcreate-agency-{uuid.uuid4().hex[:8]}", status=AgencyStatus.ACTIVE.value,
        )
        brand = Brand(
            id=uuid.uuid4(), agency_id=agency.id, name="E2E Deliverable Create Brand",
            slug=f"e2e-delcreate-brand-{uuid.uuid4().hex[:8]}", status=BrandStatus.ACTIVE.value,
        )
        db.add_all([agency, brand])

        owner_user = User(
            id=uuid.uuid4(), email=OWNER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="E2E Deliverable Owner", user_type=UserType.AGENCY_USER.value,
            is_active=True, is_verified=True,
        )
        viewer_user = User(
            id=uuid.uuid4(), email=VIEWER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="E2E Deliverable Viewer", user_type=UserType.AGENCY_USER.value,
            is_active=True, is_verified=True,
        )
        brand_user = User(
            id=uuid.uuid4(), email=BRAND_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="E2E Deliverable Brand Owner", user_type=UserType.BRAND_USER.value,
            is_active=True, is_verified=True,
        )
        db.add_all([owner_user, viewer_user, brand_user])
        await db.flush()

        db.add_all([
            AgencyMember(
                id=uuid.uuid4(), agency_id=agency.id, user_id=owner_user.id,
                role=AgencyMemberRole.OWNER.value, status=AgencyMemberStatus.ACTIVE.value,
            ),
            AgencyMember(
                id=uuid.uuid4(), agency_id=agency.id, user_id=viewer_user.id,
                role=AgencyMemberRole.VIEWER.value, status=AgencyMemberStatus.ACTIVE.value,
            ),
            BrandMember(
                id=uuid.uuid4(), brand_id=brand.id, user_id=brand_user.id,
                role=BrandMemberRole.BRAND_OWNER.value, status=BrandMemberStatus.ACTIVE.value,
            ),
        ])

        brief = Brief(
            id=uuid.uuid4(), agency_id=agency.id, brand_id=brand.id,
            title="E2E Deliverable Create Brief", status="in_production",
            created_by_id=owner_user.id,
        )
        db.add(brief)
        await db.commit()

        return agency.id, brief.id, owner_user.id


async def seed_existing_deliverable(
    agency_id: uuid.UUID, brief_id: uuid.UUID, owner_user_id: uuid.UUID
) -> str:
    """Creates the ONE deliverable that already exists on the brief before the
    spec starts — uploaded and submitted, so it's already annotatable on the
    brand portal, matching a realistic pre-existing state."""
    token = create_access_token(str(owner_user_id))
    headers = {"Authorization": f"Bearer {token}", "X-Agency-ID": str(agency_id)}

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables",
            json={"title": "Instagram Post", "deliverable_type": "image"},
            headers=headers,
        )
        resp.raise_for_status()
        deliverable_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/assets",
            headers=headers,
            files={"file": ("e2e-existing-deliverable.png", _make_fixture_png((40, 110, 190)), "image/png")},
        )
        resp.raise_for_status()

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/submit",
            headers=headers,
        )
        resp.raise_for_status()

        return deliverable_id


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
    agency_id, brief_id, owner_user_id = await seed_db()
    existing_deliverable_id = await seed_existing_deliverable(agency_id, brief_id, owner_user_id)
    print("E2E_OWNER_EMAIL=" + OWNER_EMAIL)
    print("E2E_VIEWER_EMAIL=" + VIEWER_EMAIL)
    print("E2E_BRAND_EMAIL=" + BRAND_EMAIL)
    print("E2E_PASSWORD=" + PASSWORD)
    print("E2E_BRIEF_ID=" + str(brief_id))
    print("E2E_EXISTING_DELIVERABLE_ID=" + existing_deliverable_id)
    print("__AGENCY_ID__=" + str(agency_id))


if __name__ == "__main__":
    asyncio.run(main())

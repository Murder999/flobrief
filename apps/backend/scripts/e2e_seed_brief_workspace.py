"""E2E fixture for e2e/brief-detail-workspace.spec.ts.

Creates one Agency + agency owner User, one Brand + brand owner User, a Brief
with TWO submitted image deliverables (so the version strip / thumbnail
switching in the redesigned DeliverableWorkspace has something to switch
between) plus one plain brief-level reference asset that is NOT attached to
any deliverable (so the "Brief Dosyaları ve Referansları" dedup logic has
something real to prove: the reference asset must show there, the two
deliverable assets must not).

Two modes:
  python e2e_seed_brief_workspace.py seed      -> prints E2E_* env vars
  python e2e_seed_brief_workspace.py cleanup <agency_id>  -> deletes the fixture

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production" — see _assert_local_test_database() below. This
is test-only fixture code (not application logic); it is tracked in git
(unlike the ad-hoc apps/backend/scripts/_tmp_*.py debug scripts) so the
Playwright spec that depends on it works from a clean clone.
"""

from __future__ import annotations

import asyncio
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

AGENCY_EMAIL = "flobrief-e2e-workspace-agency@example.com"
BRAND_EMAIL = "flobrief-e2e-workspace-brand@example.com"
PASSWORD = "E2eTest1234!"
API_BASE = "http://127.0.0.1:8003"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _assert_local_test_database() -> None:
    """Refuse to seed/cleanup against anything but a local, non-production DB.

    This script deletes rows by email/agency-id — safe on a disposable local
    Postgres, destructive anywhere else. Both the DB host and APP_ENV are
    checked so a misconfigured .env can't silently point this at a shared or
    production database.
    """
    host = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing to run: DATABASE_URL host {host!r} is not a local host {_LOCAL_HOSTS}. "
            "This script only seeds/cleans up a local test database."
        )
    if settings.is_production:
        raise RuntimeError("Refusing to run: APP_ENV=production.")


def _make_fixture_png(color: tuple[int, int, int]) -> bytes:
    import io

    img = Image.new("RGB", (800, 450), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PNG_V1 = _make_fixture_png((60, 120, 200))
PNG_V2 = _make_fixture_png((200, 90, 60))
PNG_REF = _make_fixture_png((120, 200, 120))


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
            await db.delete(agency)  # cascades agency_members/briefs/deliverables/assets/...
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


async def seed_db() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as db:
        agency = Agency(
            id=uuid.uuid4(),
            name="E2E Workspace Agency",
            slug=f"e2e-workspace-agency-{uuid.uuid4().hex[:8]}",
            status=AgencyStatus.ACTIVE.value,
        )
        brand = Brand(
            id=uuid.uuid4(),
            agency_id=agency.id,
            name="E2E Workspace Brand",
            slug=f"e2e-workspace-brand-{uuid.uuid4().hex[:8]}",
            status=BrandStatus.ACTIVE.value,
        )
        db.add_all([agency, brand])

        agency_user = User(
            id=uuid.uuid4(),
            email=AGENCY_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Workspace Agency Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        brand_user = User(
            id=uuid.uuid4(),
            email=BRAND_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Workspace Brand Owner",
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
            title="E2E Workspace Brief",
            status="in_production",
            created_by_id=agency_user.id,
        )
        db.add(brief)
        await db.commit()

        return agency.id, brand.id, brief.id, agency_user.id


async def seed_deliverables_and_reference(
    agency_id: uuid.UUID, brief_id: uuid.UUID, agency_user_id: uuid.UUID
) -> dict[str, str]:
    token = create_access_token(str(agency_user_id))
    headers = {"Authorization": f"Bearer {token}", "X-Agency-ID": str(agency_id)}

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        # Deliverable v1
        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables",
            json={"title": "E2E Workspace Görsel v1", "deliverable_type": "image"},
            headers=headers,
        )
        resp.raise_for_status()
        deliverable_v1_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_v1_id}/assets",
            headers=headers,
            files={"file": ("e2e-workspace-v1.png", PNG_V1, "image/png")},
        )
        resp.raise_for_status()
        asset_v1_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_v1_id}/submit",
            headers=headers,
        )
        resp.raise_for_status()

        # Deliverable v2 (submitted after v1, so it sorts as "latest")
        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables",
            json={"title": "E2E Workspace Görsel v2", "deliverable_type": "image"},
            headers=headers,
        )
        resp.raise_for_status()
        deliverable_v2_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_v2_id}/assets",
            headers=headers,
            files={"file": ("e2e-workspace-v2.png", PNG_V2, "image/png")},
        )
        resp.raise_for_status()
        asset_v2_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_v2_id}/submit",
            headers=headers,
        )
        resp.raise_for_status()

        # Plain brief-level reference asset, not attached to any deliverable.
        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/assets",
            headers=headers,
            files={"file": ("e2e-workspace-ref.png", PNG_REF, "image/png")},
        )
        resp.raise_for_status()
        reference_asset_id = resp.json()["id"]

        return {
            "deliverable_v1_id": deliverable_v1_id,
            "asset_v1_id": asset_v1_id,
            "deliverable_v2_id": deliverable_v2_id,
            "asset_v2_id": asset_v2_id,
            "reference_asset_id": reference_asset_id,
        }


async def _fixup_reference_asset_brand(asset_id: str, brand_id: uuid.UUID) -> None:
    """Make the fixture a correctly scoped, explicitly client-visible reference.

    Plain agency uploads default to ``internal`` by design. The brand portal's
    hardened asset boundary exposes only ``client_visible`` and
    ``brand_reference`` rows, so the fixture must state the intended visibility
    instead of relying on the pre-hardening list behavior.
    """
    from app.models.asset import Asset

    async with AsyncSessionLocal() as db:
        asset = await db.get(Asset, uuid.UUID(asset_id))
        if asset is not None:
            asset.brand_id = brand_id
            asset.visibility = "client_visible"
            await db.commit()


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
    agency_id, brand_id, brief_id, agency_user_id = await seed_db()
    ids = await seed_deliverables_and_reference(agency_id, brief_id, agency_user_id)
    await _fixup_reference_asset_brand(ids["reference_asset_id"], brand_id)
    print("E2E_AGENCY_EMAIL=" + AGENCY_EMAIL)
    print("E2E_BRAND_EMAIL=" + BRAND_EMAIL)
    print("E2E_PASSWORD=" + PASSWORD)
    print("E2E_BRIEF_ID=" + str(brief_id))
    print("E2E_REFERENCE_ASSET_ID=" + ids["reference_asset_id"])
    print("__AGENCY_ID__=" + str(agency_id))


if __name__ == "__main__":
    asyncio.run(main())

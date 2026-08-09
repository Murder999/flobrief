"""Tests for the Deliverable model, schemas, and status transitions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, UserType
from app.models.user import User
from app.schemas.deliverable import (
    BrandApproveDeliverableRequest,
    BrandReviseDeliverableRequest,
    DeliverableCreate,
    DeliverableRead,
    DeliverableUpdate,
)
from app.tests.conftest import agency_headers

# ── DeliverableCreate schema ─────────────────────────────────────────────────


def test_deliverable_create_minimal() -> None:
    d = DeliverableCreate(title="İnstagram Görseli")
    assert d.title == "İnstagram Görseli"
    assert d.deliverable_type == "other"
    assert d.description is None


def test_deliverable_create_strips_title() -> None:
    d = DeliverableCreate(title="  Banner Görseli  ")
    assert d.title == "Banner Görseli"


def test_deliverable_create_empty_title_raises() -> None:
    with pytest.raises(ValidationError):
        DeliverableCreate(title="   ")


def test_deliverable_create_valid_types() -> None:
    for t in ("image", "video", "text", "document", "link", "other"):
        d = DeliverableCreate(title="Test", deliverable_type=t)
        assert d.deliverable_type == t


def test_deliverable_create_invalid_type_raises() -> None:
    with pytest.raises(ValidationError):
        DeliverableCreate(title="Test", deliverable_type="audio")


def test_deliverable_create_with_description() -> None:
    d = DeliverableCreate(
        title="Video",
        deliverable_type="video",
        description="30 saniyelik reklam filmi",
        description_html="<p>30 saniyelik reklam filmi</p>",
    )
    assert d.description == "30 saniyelik reklam filmi"
    assert d.description_html is not None


# ── DeliverableUpdate schema ─────────────────────────────────────────────────


def test_deliverable_update_all_optional() -> None:
    u = DeliverableUpdate()
    assert u.title is None
    assert u.description is None
    assert u.deliverable_type is None


def test_deliverable_update_strips_title() -> None:
    u = DeliverableUpdate(title="  Yeni Başlık  ")
    assert u.title == "Yeni Başlık"


def test_deliverable_update_empty_title_raises() -> None:
    with pytest.raises(ValidationError):
        DeliverableUpdate(title="")


def test_deliverable_update_invalid_type_raises() -> None:
    with pytest.raises(ValidationError):
        DeliverableUpdate(deliverable_type="audio")


def test_deliverable_update_valid_type() -> None:
    u = DeliverableUpdate(deliverable_type="image")
    assert u.deliverable_type == "image"


# ── BrandReviseDeliverableRequest schema ────────────────────────────────────


def test_brand_revise_request_strips_reason() -> None:
    r = BrandReviseDeliverableRequest(reason="  Renk uyumsuz  ")
    assert r.reason == "Renk uyumsuz"


def test_brand_revise_request_empty_raises() -> None:
    with pytest.raises(ValidationError):
        BrandReviseDeliverableRequest(reason="   ")


def test_brand_revise_request_too_long_raises() -> None:
    with pytest.raises(ValidationError):
        BrandReviseDeliverableRequest(reason="x" * 5001)


def test_brand_revise_request_max_length_ok() -> None:
    r = BrandReviseDeliverableRequest(reason="x" * 5000)
    assert len(r.reason) == 5000


# ── BrandApproveDeliverableRequest schema ───────────────────────────────────


def test_brand_approve_request_no_note() -> None:
    r = BrandApproveDeliverableRequest()
    assert r.note is None


def test_brand_approve_request_with_note() -> None:
    r = BrandApproveDeliverableRequest(note="Harika görünüyor!")
    assert r.note == "Harika görünüyor!"


# ── DeliverableRead schema ───────────────────────────────────────────────────


def test_deliverable_read_schema() -> None:
    now = datetime.now(UTC)
    uid = uuid.uuid4()
    d = DeliverableRead(
        id=uid,
        agency_id=uid,
        brand_id=uid,
        brief_id=uid,
        title="Banner",
        description=None,
        description_html=None,
        deliverable_type="image",
        status="draft",
        version_number=1,
        revision_count=0,
        revision_note=None,
        approve_note=None,
        submitted_by_id=None,
        submitted_at=None,
        approved_by_id=None,
        approved_at=None,
        created_at=now,
        updated_at=now,
        assets=[],
    )
    assert d.status == "draft"
    assert d.version_number == 1
    assert d.revision_count == 0
    assert d.assets == []


def test_deliverable_read_submitted_status() -> None:
    now = datetime.now(UTC)
    uid = uuid.uuid4()
    d = DeliverableRead(
        id=uid,
        agency_id=uid,
        brand_id=None,
        brief_id=uid,
        title="Video Reklam",
        description="Yaz kampanyası",
        description_html="<p>Yaz kampanyası</p>",
        deliverable_type="video",
        status="submitted",
        version_number=1,
        revision_count=0,
        revision_note=None,
        approve_note=None,
        submitted_by_id=uid,
        submitted_at=now,
        approved_by_id=None,
        approved_at=None,
        created_at=now,
        updated_at=now,
        assets=[],
    )
    assert d.status == "submitted"
    assert d.submitted_by_id == uid
    assert d.submitted_at == now


def test_deliverable_read_approved_status() -> None:
    now = datetime.now(UTC)
    uid = uuid.uuid4()
    d = DeliverableRead(
        id=uid,
        agency_id=uid,
        brand_id=uid,
        brief_id=uid,
        title="Onaylanan İçerik",
        description=None,
        description_html=None,
        deliverable_type="image",
        status="approved",
        version_number=2,
        revision_count=1,
        revision_note="İlk versiyon reddedildi",
        approve_note="Mükemmel!",
        submitted_by_id=uid,
        submitted_at=now,
        approved_by_id=uid,
        approved_at=now,
        created_at=now,
        updated_at=now,
        assets=[],
    )
    assert d.status == "approved"
    assert d.revision_count == 1
    assert d.approve_note == "Mükemmel!"


# ── Status flow validation ───────────────────────────────────────────────────


def test_deliverable_statuses_cover_full_lifecycle() -> None:
    valid_statuses = {
        "draft",
        "submitted",
        "revision_requested",
        "approved",
        "rejected",
        "archived",
    }
    for s in valid_statuses:
        d = DeliverableRead(
            id=uuid.uuid4(),
            agency_id=uuid.uuid4(),
            brand_id=None,
            brief_id=uuid.uuid4(),
            title="T",
            description=None,
            description_html=None,
            deliverable_type="other",
            status=s,
            version_number=1,
            revision_count=0,
            revision_note=None,
            approve_note=None,
            submitted_by_id=None,
            submitted_at=None,
            approved_by_id=None,
            approved_at=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            assets=[],
        )
        assert d.status == s


# ── Deliverable model import ─────────────────────────────────────────────────


def test_deliverable_model_importable() -> None:
    from app.models.deliverable import Deliverable

    assert Deliverable.__tablename__ == "deliverables"


def test_deliverable_model_in_init() -> None:
    from app.models import Deliverable

    assert Deliverable is not None


def test_asset_model_has_visibility() -> None:
    from app.models.asset import Asset

    assert hasattr(Asset, "visibility")


def test_asset_link_model_has_deliverable_id() -> None:
    from app.models.asset import AssetLink

    assert hasattr(AssetLink, "deliverable_id")


# ── Create-deliverable RBAC (second independent deliverable on a brief) ─────
#
# Regression coverage for the missing "add a second deliverable" action: the
# create endpoint previously had no permission dependency at all, so any
# agency member — including VIEWER — could call it directly even though the
# UI never exposed a way to. Mirrors the pattern in test_time_entry_rbac.py.


async def _add_agency_member(agency_id: uuid.UUID, role: str) -> str:
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"{role}-{uuid.uuid4().hex[:8]}@test.local",
            password_hash="not-a-real-hash-test-fixture-only",
            full_name=f"Test {role}",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        session.add(
            AgencyMember(
                id=uuid.uuid4(),
                agency_id=agency_id,
                user_id=user.id,
                role=role,
                status=AgencyMemberStatus.ACTIVE.value,
            )
        )
        await session.commit()
        return create_access_token(str(user.id))


@pytest.mark.asyncio
async def test_viewer_cannot_create_deliverable(client, tenants) -> None:
    tenant_a, _ = tenants
    viewer_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.VIEWER.value)
    headers = agency_headers(viewer_token, tenant_a.agency_id)

    resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/deliverables",
        headers=headers,
        json={"title": "Yetkisiz Deliverable", "deliverable_type": "image"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_designer_can_create_second_independent_deliverable(client, tenants) -> None:
    """tenant_a already has one seeded deliverable on tenant_a.brief_id — a
    DESIGNER (holds brief:create) must be able to add an independent second
    one, e.g. an Instagram post alongside a LinkedIn design."""
    tenant_a, _ = tenants
    designer_token = await _add_agency_member(tenant_a.agency_id, AgencyMemberRole.DESIGNER.value)
    headers = agency_headers(designer_token, tenant_a.agency_id)

    resp = await client.post(
        f"/api/v1/briefs/{tenant_a.brief_id}/deliverables",
        headers=headers,
        json={"title": "LinkedIn Tasarımı", "deliverable_type": "image"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "LinkedIn Tasarımı"

    list_resp = await client.get(
        f"/api/v1/briefs/{tenant_a.brief_id}/deliverables", headers=headers
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 2

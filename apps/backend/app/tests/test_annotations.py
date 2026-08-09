"""Tests for image annotation (revision marker) schemas, models, and endpoint auth.

Covers pure schema/model validation plus auth-layer checks that reject before any
DB call (no token / invalid token -> 401). Real tenant-isolation and IDOR
verification against live rows (cross-tenant access, the reopen authorization
matrix, unrelated-deliverable annotation-ID reuse) lives in
test_annotation_tenant_isolation.py, which drives the app end to end against a
real Postgres database.
"""

from __future__ import annotations

import math
import uuid

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.schemas.deliverable_annotation import (
    AnnotationCreate,
    AnnotationReplyCreate,
    AnnotationUpdateStatus,
)

# ── AnnotationCreate schema ──────────────────────────────────────────────────


def test_annotation_create_minimal() -> None:
    a = AnnotationCreate(body="Logo daha büyük olsun")
    assert a.body == "Logo daha büyük olsun"
    assert a.version_number == 1
    assert a.annotation_type == "general"
    assert a.visibility == "client_visible"
    assert a.x_percent is None
    assert a.y_percent is None


def test_annotation_create_strips_body() -> None:
    a = AnnotationCreate(body="  Rengi değiştirin  ")
    assert a.body == "Rengi değiştirin"


def test_annotation_create_empty_body_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationCreate(body="   ")


def test_annotation_create_body_too_long_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationCreate(body="x" * 10_001)


def test_annotation_create_body_max_length_ok() -> None:
    a = AnnotationCreate(body="x" * 10_000)
    assert len(a.body) == 10_000


def test_annotation_create_valid_types() -> None:
    for t in ("general", "revision", "approval_note"):
        a = AnnotationCreate(body="test", annotation_type=t)
        assert a.annotation_type == t


def test_annotation_create_invalid_type_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationCreate(body="test", annotation_type="bug")


def test_annotation_create_valid_visibilities() -> None:
    for v in ("internal", "client_visible"):
        a = AnnotationCreate(body="test", visibility=v)
        assert a.visibility == v


def test_annotation_create_invalid_visibility_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationCreate(body="test", visibility="public")


# ── Coordinate validation (normalized 0-100 percent, letterbox-safe) ────────


def test_annotation_create_coordinate_boundaries_ok() -> None:
    a = AnnotationCreate(body="test", x_percent=0.0, y_percent=100.0)
    assert a.x_percent == 0.0
    assert a.y_percent == 100.0


def test_annotation_create_coordinate_midpoint_ok() -> None:
    a = AnnotationCreate(body="test", x_percent=42.5, y_percent=57.25)
    assert a.x_percent == 42.5
    assert a.y_percent == 57.25


def test_annotation_create_coordinate_negative_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationCreate(body="test", x_percent=-0.01, y_percent=50)


def test_annotation_create_coordinate_over_100_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationCreate(body="test", x_percent=50, y_percent=100.01)


def test_annotation_create_coordinate_nan_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationCreate(body="test", x_percent=math.nan, y_percent=50)


def test_annotation_create_coordinate_infinity_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationCreate(body="test", x_percent=50, y_percent=math.inf)


def test_annotation_create_coordinate_negative_infinity_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationCreate(body="test", x_percent=-math.inf, y_percent=50)


def test_annotation_create_no_coordinates_allowed() -> None:
    # A text-only annotation (no pin) is still valid — coordinates are optional.
    a = AnnotationCreate(body="Genel not")
    assert a.x_percent is None
    assert a.y_percent is None


# ── AnnotationReplyCreate schema ─────────────────────────────────────────────


def test_annotation_reply_strips_body() -> None:
    r = AnnotationReplyCreate(body="  Düzeltildi  ")
    assert r.body == "Düzeltildi"


def test_annotation_reply_empty_body_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationReplyCreate(body="   ")


def test_annotation_reply_too_long_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationReplyCreate(body="x" * 10_001)


def test_annotation_reply_invalid_visibility_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationReplyCreate(body="ok", visibility="everyone")


def test_annotation_reply_default_visibility_client_visible() -> None:
    r = AnnotationReplyCreate(body="ok")
    assert r.visibility == "client_visible"


# ── AnnotationUpdateStatus schema ────────────────────────────────────────────


def test_annotation_update_status_valid_values() -> None:
    for s in ("open", "resolved"):
        u = AnnotationUpdateStatus(status=s)
        assert u.status == s


def test_annotation_update_status_invalid_raises() -> None:
    with pytest.raises(ValidationError):
        AnnotationUpdateStatus(status="archived")


# ── Model shape ───────────────────────────────────────────────────────────────


def test_deliverable_annotation_model_importable() -> None:
    from app.models.deliverable_annotation import DeliverableAnnotation

    assert DeliverableAnnotation.__tablename__ == "deliverable_annotations"


def test_annotation_reply_model_importable() -> None:
    from app.models.deliverable_annotation import AnnotationReply

    assert AnnotationReply.__tablename__ == "annotation_replies"


def test_deliverable_annotation_has_stable_numbering_field() -> None:
    from app.models.deliverable_annotation import DeliverableAnnotation

    assert hasattr(DeliverableAnnotation, "label_number")
    assert hasattr(DeliverableAnnotation, "version_number")


def test_deliverable_annotation_has_tenant_scoping_fields() -> None:
    from app.models.deliverable_annotation import DeliverableAnnotation

    assert hasattr(DeliverableAnnotation, "agency_id")
    assert hasattr(DeliverableAnnotation, "brand_id")
    assert hasattr(DeliverableAnnotation, "brief_id")
    assert hasattr(DeliverableAnnotation, "deliverable_id")
    assert hasattr(DeliverableAnnotation, "asset_id")


def test_deliverable_annotation_has_resolve_lifecycle_fields() -> None:
    from app.models.deliverable_annotation import DeliverableAnnotation

    assert hasattr(DeliverableAnnotation, "status")
    assert hasattr(DeliverableAnnotation, "resolved_by_id")
    assert hasattr(DeliverableAnnotation, "resolved_at")


# ── Notification event enum ──────────────────────────────────────────────────


def test_annotation_notification_event_values() -> None:
    from app.models.enums import NotificationEventType

    assert NotificationEventType.ANNOTATION_CREATED == "annotation.created"
    assert NotificationEventType.ANNOTATION_RESOLVED == "annotation.resolved"
    assert NotificationEventType.ANNOTATION_REPLIED == "annotation.replied"
    assert NotificationEventType.ANNOTATION_REOPENED == "annotation.reopened"


# ── Auth-layer security (DB-agnostic: rejected before any DB call) ──────────
#
# Mirrors test_security_audit.py's approach: unauthenticated / malformed-token
# requests to tenant-scoped and brand-portal-scoped endpoints must be rejected
# by the JWT layer before any annotation row could ever be read or written —
# this is the IDOR/unauthorized-access baseline that holds regardless of what
# annotation ID an attacker guesses.


class TestAgencyAnnotationEndpointsRejectUnauthenticated:
    @pytest.mark.asyncio
    async def test_list_annotations_no_token_rejected(self, client: AsyncClient) -> None:
        brief_id = uuid.uuid4()
        deliverable_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/annotations",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_annotation_no_token_rejected(self, client: AsyncClient) -> None:
        brief_id = uuid.uuid4()
        deliverable_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/annotations",
            json={"body": "test", "x_percent": 10, "y_percent": 20},
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_resolve_annotation_no_token_rejected(self, client: AsyncClient) -> None:
        annotation_id = uuid.uuid4()
        deliverable_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/annotations/{annotation_id}/resolve?deliverable_id={deliverable_id}",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_reopen_annotation_no_token_rejected(self, client: AsyncClient) -> None:
        annotation_id = uuid.uuid4()
        deliverable_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/annotations/{annotation_id}/reopen?deliverable_id={deliverable_id}",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_reply_annotation_no_token_rejected(self, client: AsyncClient) -> None:
        annotation_id = uuid.uuid4()
        deliverable_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/annotations/{annotation_id}/replies?deliverable_id={deliverable_id}",
            json={"body": "yanıt"},
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_on_annotation_endpoint_rejected(self, client: AsyncClient) -> None:
        brief_id = uuid.uuid4()
        deliverable_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/annotations",
            headers={
                "Authorization": "Bearer not-a-real-jwt",
                "X-Agency-ID": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 401


class TestBrandAnnotationEndpointsRejectUnauthenticated:
    @pytest.mark.asyncio
    async def test_list_brand_annotations_no_token_rejected(self, client: AsyncClient) -> None:
        deliverable_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/brand-portal/deliverables/{deliverable_id}/annotations")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_brand_annotation_no_token_rejected(self, client: AsyncClient) -> None:
        deliverable_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/brand-portal/deliverables/{deliverable_id}/annotations",
            json={"body": "revize istiyorum", "x_percent": 30, "y_percent": 40},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_reply_brand_annotation_no_token_rejected(self, client: AsyncClient) -> None:
        annotation_id = uuid.uuid4()
        deliverable_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/brand-portal/annotations/{annotation_id}/replies?deliverable_id={deliverable_id}",
            json={"body": "yanıt"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_reopen_brand_annotation_no_token_rejected(self, client: AsyncClient) -> None:
        """New endpoint added for spec requirement: brand can reopen a resolved revision."""
        annotation_id = uuid.uuid4()
        deliverable_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/brand-portal/annotations/{annotation_id}/reopen?deliverable_id={deliverable_id}",
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_on_brand_annotation_endpoint_rejected(
        self, client: AsyncClient
    ) -> None:
        deliverable_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/brand-portal/deliverables/{deliverable_id}/annotations",
            headers={"Authorization": "Bearer garbage-token"},
        )
        assert resp.status_code == 401

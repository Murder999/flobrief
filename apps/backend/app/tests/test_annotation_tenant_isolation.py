"""Live-database integration tests for annotation IDOR / tenant isolation and the
reopen authorization matrix.

Unlike test_annotations.py (pure schema + pre-DB auth-layer checks), these tests
create real Agency/Brand/User/Brief/Deliverable/Annotation rows in a live Postgres
database (see the `tenants` fixture in conftest.py) and drive the actual FastAPI
app end to end with real JWTs, so a tenant-scoping regression (e.g. a missing
`agency_id ==` / `brand_id ==` filter) would actually fail a test instead of
relying on manual curl verification.

Requires a running Postgres reachable at $DATABASE_URL with the current schema
applied (`alembic upgrade head`). Never touches production data — point
DATABASE_URL at a disposable database (see CI: a dedicated `flobrief_test`
Postgres service container, isolated from any dev/prod database).
"""

from __future__ import annotations

from httpx import AsyncClient

from app.db.session import AsyncSessionLocal
from app.models.deliverable_annotation import DeliverableAnnotation
from app.tests.conftest import agency_headers, brand_headers


class TestCrossTenantIsolation:
    async def test_list_annotations_cross_tenant_denied(self, client: AsyncClient, tenants) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.get(
            f"/api/v1/briefs/{tenant_b.brief_id}/deliverables/{tenant_b.deliverable_id}/annotations",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 404

    async def test_reply_annotation_cross_tenant_denied(self, client: AsyncClient, tenants) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.post(
            f"/api/v1/annotations/{tenant_b.annotation_id}/replies"
            f"?deliverable_id={tenant_b.deliverable_id}",
            json={"body": "cross-tenant reply attempt"},
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 404

    async def test_resolve_annotation_cross_tenant_denied(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.post(
            f"/api/v1/annotations/{tenant_b.annotation_id}/resolve"
            f"?deliverable_id={tenant_b.deliverable_id}",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 404

    async def test_reopen_annotation_cross_tenant_denied(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.post(
            f"/api/v1/annotations/{tenant_b.annotation_id}/reopen"
            f"?deliverable_id={tenant_b.deliverable_id}",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 403

    async def test_annotation_id_rejected_for_unrelated_deliverable_same_tenant(
        self, client: AsyncClient, tenants
    ) -> None:
        """Same tenant, but the annotation belongs to a different brief/deliverable —
        the deliverable_id path/query param must be validated against the annotation
        row, not just the agency_id."""
        tenant_a, _ = tenants
        resp = await client.post(
            f"/api/v1/annotations/{tenant_a.annotation_id}/resolve"
            f"?deliverable_id={tenant_a.other_deliverable_id}",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 404


class TestReopenAuthorizationMatrix:
    async def test_agency_reopen_own_tenant_denied_403(self, client: AsyncClient, tenants) -> None:
        """Regression test: agency workspace members must never be able to reopen
        a resolved revision, even within their own tenant — only a brand manager/
        owner may (see brand_portal.reopen_brand_annotation)."""
        tenant_a, _ = tenants
        resp = await client.post(
            f"/api/v1/annotations/{tenant_a.annotation_id}/reopen"
            f"?deliverable_id={tenant_a.deliverable_id}",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 403

    async def test_unauthorized_brand_user_cannot_reopen(
        self, client: AsyncClient, tenants
    ) -> None:
        """brand_viewer is not a manager/owner — must be denied."""
        tenant_a, _ = tenants
        resp = await client.post(
            f"/api/v1/brand-portal/annotations/{tenant_a.annotation_id}/reopen"
            f"?deliverable_id={tenant_a.deliverable_id}",
            headers=brand_headers(tenant_a.brand_viewer_token),
        )
        assert resp.status_code == 403

    async def test_authorized_brand_manager_can_reopen(self, client: AsyncClient, tenants) -> None:
        """Positive control: the one role that IS allowed to reopen actually can —
        proves the 403s above are real authorization checks, not a blanket denial."""
        tenant_a, _ = tenants
        resp = await client.post(
            f"/api/v1/brand-portal/annotations/{tenant_a.annotation_id}/reopen"
            f"?deliverable_id={tenant_a.deliverable_id}",
            headers=brand_headers(tenant_a.brand_manager_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "open"

    async def test_agency_can_resolve_own_tenant_annotation(
        self, client: AsyncClient, tenants
    ) -> None:
        """Positive control: agency users must still be able to resolve their own
        tenant's revisions — only reopen is brand-exclusive."""
        tenant_a, _ = tenants
        async with AsyncSessionLocal() as session:
            ann = await session.get(DeliverableAnnotation, tenant_a.annotation_id)
            ann.status = "open"
            await session.commit()

        resp = await client.post(
            f"/api/v1/annotations/{tenant_a.annotation_id}/resolve"
            f"?deliverable_id={tenant_a.deliverable_id}",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    async def test_agency_can_reply_own_tenant_annotation(
        self, client: AsyncClient, tenants
    ) -> None:
        """Positive control: agency users must still be able to reply."""
        tenant_a, _ = tenants
        resp = await client.post(
            f"/api/v1/annotations/{tenant_a.annotation_id}/replies"
            f"?deliverable_id={tenant_a.deliverable_id}",
            json={"body": "agency reply"},
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 201


class TestBrandPortalCrossTenantIsolation:
    async def test_brand_cannot_list_other_brand_annotations(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.get(
            f"/api/v1/brand-portal/deliverables/{tenant_b.deliverable_id}/annotations",
            headers=brand_headers(tenant_a.brand_manager_token),
        )
        assert resp.status_code == 404

    async def test_brand_cannot_reply_other_brand_annotation(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.post(
            f"/api/v1/brand-portal/annotations/{tenant_b.annotation_id}/replies"
            f"?deliverable_id={tenant_b.deliverable_id}",
            json={"body": "cross-brand reply attempt"},
            headers=brand_headers(tenant_a.brand_manager_token),
        )
        assert resp.status_code == 404

    async def test_brand_manager_cannot_reopen_other_brand_annotation(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.post(
            f"/api/v1/brand-portal/annotations/{tenant_b.annotation_id}/reopen"
            f"?deliverable_id={tenant_b.deliverable_id}",
            headers=brand_headers(tenant_a.brand_manager_token),
        )
        assert resp.status_code == 404

"""Cross-tenant IDOR tests for the Preview Center, mirroring
test_annotation_tenant_isolation.py: agency A must never be able to read or
write tenant B's preview config/slots, and brand users must never see
another brand's preview data — even brand-portal read-only access is scoped.
"""

from __future__ import annotations

import io

from httpx import AsyncClient
from PIL import Image

from app.tests.conftest import agency_headers, brand_headers


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 400), color=(1, 1, 1)).save(buf, format="PNG")
    return buf.getvalue()


async def _create_draft_deliverable(client: AsyncClient, tenant, headers) -> str:
    resp = await client.post(
        f"/api/v1/briefs/{tenant.brief_id}/deliverables",
        headers=headers,
        json={"title": "Tenant Isolation Deliverable", "deliverable_type": "image"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


class TestAgencyCrossTenantIsolation:
    async def test_get_preview_config_cross_tenant_denied(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.get(
            f"/api/v1/briefs/{tenant_b.brief_id}/deliverables/{tenant_b.deliverable_id}"
            "/preview-config",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 404

    async def test_put_preview_config_cross_tenant_denied(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.put(
            f"/api/v1/briefs/{tenant_b.brief_id}/deliverables/{tenant_b.deliverable_id}"
            "/preview-config",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
            json={"platform": "instagram", "preview_format": "feed_single"},
        )
        assert resp.status_code == 404

    async def test_list_preview_slots_cross_tenant_denied(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.get(
            f"/api/v1/briefs/{tenant_b.brief_id}/deliverables/{tenant_b.deliverable_id}"
            "/preview-slots",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 404

    async def test_reorder_slots_cross_tenant_denied(self, client: AsyncClient, tenants) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.put(
            f"/api/v1/briefs/{tenant_b.brief_id}/deliverables/{tenant_b.deliverable_id}"
            "/preview-slots",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
            json={"slots": []},
        )
        assert resp.status_code == 404

    async def test_same_tenant_wrong_brief_path_denied(self, client: AsyncClient, tenants) -> None:
        """Same agency, but the deliverable belongs to a different brief —
        the brief_id in the path must be validated against the deliverable row."""
        tenant_a, _ = tenants
        resp = await client.get(
            f"/api/v1/briefs/{tenant_a.other_brief_id}/deliverables/{tenant_a.deliverable_id}"
            "/preview-config",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 404


class TestBrandPortalCrossTenantIsolation:
    async def test_brand_cannot_read_other_brand_preview_config(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.get(
            f"/api/v1/brand-portal/briefs/{tenant_b.brief_id}/deliverables/"
            f"{tenant_b.deliverable_id}/preview-config",
            headers=brand_headers(tenant_a.brand_manager_token),
        )
        assert resp.status_code == 404

    async def test_brand_cannot_list_other_brand_preview_slots(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, tenant_b = tenants
        resp = await client.get(
            f"/api/v1/brand-portal/briefs/{tenant_b.brief_id}/deliverables/"
            f"{tenant_b.deliverable_id}/preview-slots",
            headers=brand_headers(tenant_a.brand_manager_token),
        )
        assert resp.status_code == 404

    async def test_brand_cannot_see_draft_deliverable_preview(
        self, client: AsyncClient, tenants
    ) -> None:
        """Brands never see draft deliverables at all — configuring a preview
        on a draft must not leak it early."""
        tenant_a, _ = tenants
        agency_hdrs = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        deliverable_id = await _create_draft_deliverable(client, tenant_a, agency_hdrs)
        await client.put(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}/preview-config",
            headers=agency_hdrs,
            json={"platform": "instagram", "preview_format": "feed_single"},
        )
        resp = await client.get(
            f"/api/v1/brand-portal/briefs/{tenant_a.brief_id}/deliverables/{deliverable_id}"
            "/preview-config",
            headers=brand_headers(tenant_a.brand_manager_token),
        )
        assert resp.status_code == 404

    async def test_brand_can_read_own_submitted_deliverable_preview(
        self, client: AsyncClient, tenants
    ) -> None:
        """Positive control: the brand manager CAN read a preview config for
        their own brand's submitted deliverable — proves the 404s above are
        real tenant/status scoping, not a blanket denial."""
        tenant_a, _ = tenants
        # tenant_a.deliverable_id is pre-seeded as status="submitted"
        # Directly seed a config via DB since the edit guard blocks agency
        # PUT once submitted — this exercises brand-side read only.
        from app.db.session import AsyncSessionLocal
        from app.models.deliverable_preview import DeliverablePreviewConfig

        async with AsyncSessionLocal() as session:
            config = DeliverablePreviewConfig(
                agency_id=tenant_a.agency_id,
                brand_id=tenant_a.brand_id,
                brief_id=tenant_a.brief_id,
                deliverable_id=tenant_a.deliverable_id,
                platform="instagram",
                preview_format="feed_single",
                caption="Gerçek başlık",
            )
            session.add(config)
            await session.commit()

        resp = await client.get(
            f"/api/v1/brand-portal/briefs/{tenant_a.brief_id}/deliverables/"
            f"{tenant_a.deliverable_id}/preview-config",
            headers=brand_headers(tenant_a.brand_manager_token),
        )
        assert resp.status_code == 200
        assert resp.json()["platform"] == "instagram"


class TestApproveAuthorizationForPreviewedDeliverable:
    """The Preview Center's "approve" action is not a preview-router endpoint —
    it reuses the existing brand_portal.approve_deliverable (see
    deliverable_preview.py's module docstring: "Composition, not a parallel
    authority"). Covering it here closes the gap that none of the three
    preview test files previously exercised its is_manager gate or its
    tenant scoping, even though it is the terminal action of every preview
    review."""

    async def test_brand_viewer_cannot_approve_own_tenant_deliverable(
        self, client: AsyncClient, tenants
    ) -> None:
        """brand_viewer is not a manager/owner — must be denied, same
        authorization class as the reopen matrix in
        test_annotation_tenant_isolation.py."""
        tenant_a, _ = tenants
        resp = await client.post(
            f"/api/v1/brand-portal/briefs/{tenant_a.brief_id}/deliverables/"
            f"{tenant_a.deliverable_id}/approve",
            headers=brand_headers(tenant_a.brand_viewer_token),
            json={},
        )
        assert resp.status_code == 403

    async def test_brand_manager_can_approve_own_tenant_submitted_deliverable(
        self, client: AsyncClient, tenants
    ) -> None:
        """Positive control: proves the 403/404 in this class are real
        authorization checks, not a blanket denial."""
        tenant_a, _ = tenants
        resp = await client.post(
            f"/api/v1/brand-portal/briefs/{tenant_a.brief_id}/deliverables/"
            f"{tenant_a.deliverable_id}/approve",
            headers=brand_headers(tenant_a.brand_manager_token),
            json={},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_brand_manager_cannot_approve_other_brand_deliverable(
        self, client: AsyncClient, tenants
    ) -> None:
        """Cross-brand IDOR: tenant_a's manager must never approve tenant_b's
        deliverable, even though both are otherwise identically-shaped
        submitted deliverables."""
        tenant_a, tenant_b = tenants
        resp = await client.post(
            f"/api/v1/brand-portal/briefs/{tenant_b.brief_id}/deliverables/"
            f"{tenant_b.deliverable_id}/approve",
            headers=brand_headers(tenant_a.brand_manager_token),
            json={},
        )
        assert resp.status_code == 404

    async def test_agency_workspace_member_cannot_hit_brand_approve_endpoint(
        self, client: AsyncClient, tenants
    ) -> None:
        """The brand-portal approve endpoint requires a brand_portal_context —
        an agency JWT (no brand membership) must not be able to authenticate
        against it at all."""
        tenant_a, _ = tenants
        resp = await client.post(
            f"/api/v1/brand-portal/briefs/{tenant_a.brief_id}/deliverables/"
            f"{tenant_a.deliverable_id}/approve",
            headers=brand_headers(tenant_a.agency_token),
            json={},
        )
        assert resp.status_code == 403

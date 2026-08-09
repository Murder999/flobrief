"""Regression coverage for the deliverable "latest version" computation.

Root cause being guarded against: the old frontend logic treated every
deliverable on a brief as one shared version timeline (only the
most-recently-created deliverable in the whole brief was "latest"), which
incorrectly forced independent, still-active deliverables (e.g. an
Instagram post and a LinkedIn design submitted under the same brief) into
read-only mode. The fix computes "latest" per title-chain
(app/services/deliverable_versioning.py), shared by both the agency and
brand portals, with no schema/migration change.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.tests.conftest import agency_headers, brand_headers


async def _create_and_submit(
    client: AsyncClient, brief_id, title: str, headers: dict[str, str]
) -> str:
    resp = await client.post(
        f"/api/v1/briefs/{brief_id}/deliverables",
        headers=headers,
        json={"title": title, "deliverable_type": "image"},
    )
    assert resp.status_code == 201
    deliverable_id = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/briefs/{brief_id}/deliverables/{deliverable_id}/submit",
        headers=headers,
    )
    assert resp.status_code == 200
    return deliverable_id


class TestIndependentDeliverablesAreAllLatest:
    """Two siblings with distinct titles are never a version chain of each
    other — both must report is_latest_version=True, on both portals."""

    async def test_two_independent_deliverables_both_latest_agency_side(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        hdrs = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        ig_id = await _create_and_submit(client, tenant_a.brief_id, "Instagram Post", hdrs)
        li_id = await _create_and_submit(client, tenant_a.brief_id, "LinkedIn Görsel", hdrs)

        resp = await client.get(f"/api/v1/briefs/{tenant_a.brief_id}/deliverables", headers=hdrs)
        assert resp.status_code == 200
        by_id = {d["id"]: d for d in resp.json()}
        assert by_id[ig_id]["is_latest_version"] is True
        assert by_id[li_id]["is_latest_version"] is True

    async def test_two_independent_deliverables_both_latest_brand_side(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        agency_hdrs = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        ig_id = await _create_and_submit(client, tenant_a.brief_id, "Instagram Story", agency_hdrs)
        video_id = await _create_and_submit(
            client, tenant_a.brief_id, "Kampanya Videosu", agency_hdrs
        )

        resp = await client.get(
            f"/api/v1/brand-portal/briefs/{tenant_a.brief_id}/deliverables",
            headers=brand_headers(tenant_a.brand_manager_token),
        )
        assert resp.status_code == 200
        by_id = {d["id"]: d for d in resp.json()}
        assert by_id[ig_id]["is_latest_version"] is True
        assert by_id[video_id]["is_latest_version"] is True
        # Both are annotatable — the specific regression this closes.
        for did in (ig_id, video_id):
            resp = await client.post(
                f"/api/v1/brand-portal/deliverables/{did}/annotations",
                headers=brand_headers(tenant_a.brand_manager_token),
                json={"body": "Beğendim ama küçük bir not", "annotation_type": "general"},
            )
            assert resp.status_code == 201, resp.text


class TestSameTitleChainOnlyNewestIsLatest:
    """Two rows sharing an exact (normalized) title represent the same
    logical deliverable resubmitted over time — only the newer one is
    latest; the older is a genuine historical version."""

    async def test_older_same_title_row_is_not_latest_on_either_portal(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        agency_hdrs = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        old_id = await _create_and_submit(client, tenant_a.brief_id, "  Ürün Banner  ", agency_hdrs)
        new_id = await _create_and_submit(client, tenant_a.brief_id, "ürün banner", agency_hdrs)
        assert old_id != new_id

        agency_resp = await client.get(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables", headers=agency_hdrs
        )
        by_id = {d["id"]: d for d in agency_resp.json()}
        assert by_id[old_id]["is_latest_version"] is False
        assert by_id[new_id]["is_latest_version"] is True

        brand_resp = await client.get(
            f"/api/v1/brand-portal/briefs/{tenant_a.brief_id}/deliverables",
            headers=brand_headers(tenant_a.brand_manager_token),
        )
        brand_by_id = {d["id"]: d for d in brand_resp.json()}
        assert brand_by_id[old_id]["is_latest_version"] is False
        assert brand_by_id[new_id]["is_latest_version"] is True

    async def test_annotation_mutation_blocked_on_old_version_allowed_on_new(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        agency_hdrs = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        old_id = await _create_and_submit(client, tenant_a.brief_id, "Story Görseli", agency_hdrs)
        new_id = await _create_and_submit(client, tenant_a.brief_id, "Story Görseli", agency_hdrs)

        brand_hdrs = brand_headers(tenant_a.brand_manager_token)
        blocked = await client.post(
            f"/api/v1/brand-portal/deliverables/{old_id}/annotations",
            headers=brand_hdrs,
            json={"body": "Bunu değiştirelim", "annotation_type": "revision"},
        )
        assert blocked.status_code == 400

        allowed = await client.post(
            f"/api/v1/brand-portal/deliverables/{new_id}/annotations",
            headers=brand_hdrs,
            json={"body": "Bunu değiştirelim", "annotation_type": "revision"},
        )
        assert allowed.status_code == 201

    async def test_approve_and_revise_blocked_on_old_version(
        self, client: AsyncClient, tenants
    ) -> None:
        """Both rows submitted (an edge case, but reachable if an agency
        resubmits before the brand acts on the first) — approval/revision
        must only ever be possible against the latest of the pair."""
        tenant_a, _ = tenants
        agency_hdrs = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        old_id = await _create_and_submit(client, tenant_a.brief_id, "Reklam Görseli", agency_hdrs)
        new_id = await _create_and_submit(client, tenant_a.brief_id, "Reklam Görseli", agency_hdrs)

        brand_hdrs = brand_headers(tenant_a.brand_manager_token)

        approve_old = await client.post(
            f"/api/v1/brand-portal/briefs/{tenant_a.brief_id}/deliverables/{old_id}/approve",
            headers=brand_hdrs,
            json={},
        )
        assert approve_old.status_code == 400

        revise_old = await client.post(
            f"/api/v1/brand-portal/briefs/{tenant_a.brief_id}/deliverables/{old_id}"
            "/request-revision",
            headers=brand_hdrs,
            json={"reason": "Renkler uymuyor"},
        )
        assert revise_old.status_code == 400

        approve_new = await client.post(
            f"/api/v1/brand-portal/briefs/{tenant_a.brief_id}/deliverables/{new_id}/approve",
            headers=brand_hdrs,
            json={},
        )
        assert approve_new.status_code == 200
        assert approve_new.json()["status"] == "approved"

    async def test_approval_on_new_version_does_not_mutate_old_version(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        agency_hdrs = agency_headers(tenant_a.agency_token, tenant_a.agency_id)
        old_id = await _create_and_submit(client, tenant_a.brief_id, "Afiş Taslağı", agency_hdrs)
        new_id = await _create_and_submit(client, tenant_a.brief_id, "Afiş Taslağı", agency_hdrs)

        brand_hdrs = brand_headers(tenant_a.brand_manager_token)
        await client.post(
            f"/api/v1/brand-portal/briefs/{tenant_a.brief_id}/deliverables/{new_id}/approve",
            headers=brand_hdrs,
            json={},
        )

        agency_resp = await client.get(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables", headers=agency_hdrs
        )
        by_id = {d["id"]: d for d in agency_resp.json()}
        assert by_id[new_id]["status"] == "approved"
        # The old row was never touched by the new row's approval.
        assert by_id[old_id]["status"] == "submitted"
        assert by_id[old_id]["approved_at"] is None


class TestVersionChainDoesNotLeakAcrossTenants:
    """Two different agencies both naming a deliverable identically must
    never be grouped into the same chain — grouping is scoped to a single
    brief_id, which is itself already tenant-scoped."""

    async def test_same_title_different_tenants_both_latest(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, tenant_b = tenants
        a_id = await _create_and_submit(
            client,
            tenant_a.brief_id,
            "Ortak İsimli Görsel",
            agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        b_id = await _create_and_submit(
            client,
            tenant_b.brief_id,
            "Ortak İsimli Görsel",
            agency_headers(tenant_b.agency_token, tenant_b.agency_id),
        )

        resp_a = await client.get(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables",
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        resp_b = await client.get(
            f"/api/v1/briefs/{tenant_b.brief_id}/deliverables",
            headers=agency_headers(tenant_b.agency_token, tenant_b.agency_id),
        )
        by_id_a = {d["id"]: d for d in resp_a.json()}
        by_id_b = {d["id"]: d for d in resp_b.json()}
        assert by_id_a[a_id]["is_latest_version"] is True
        assert by_id_b[b_id]["is_latest_version"] is True

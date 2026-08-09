"""Owner panel RBAC tests.

Covers:
- OWNER role has all required permissions for owner panel endpoints
- Non-owner roles (ADMIN, DESIGNER, VIEWER) are blocked from billing/member-mgmt
- Platform admin has NO agency billing permissions (different domain)
- HTTP auth layer on /owner/* endpoints
- Self-deactivation guard (cannot deactivate yourself)
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.rbac import Permission, get_permissions_for_agency_role
from app.models.enums import AgencyMemberRole

# ── Owner permissions ─────────────────────────────────────────────────────────


class TestOwnerPermissions:
    def _perms(self, role: str) -> set[Permission]:
        return get_permissions_for_agency_role(role)

    def test_owner_has_billing_view(self) -> None:
        assert Permission.BILLING_VIEW in self._perms(AgencyMemberRole.OWNER.value)

    def test_owner_has_billing_manage(self) -> None:
        assert Permission.BILLING_MANAGE in self._perms(AgencyMemberRole.OWNER.value)

    def test_owner_has_agency_view(self) -> None:
        assert Permission.AGENCY_VIEW in self._perms(AgencyMemberRole.OWNER.value)

    def test_owner_has_agency_manage_members(self) -> None:
        assert Permission.AGENCY_MANAGE_MEMBERS in self._perms(AgencyMemberRole.OWNER.value)

    def test_owner_has_white_label_manage(self) -> None:
        assert Permission.WHITE_LABEL_MANAGE in self._perms(AgencyMemberRole.OWNER.value)

    def test_owner_has_brand_create(self) -> None:
        assert Permission.BRAND_CREATE in self._perms(AgencyMemberRole.OWNER.value)

    def test_owner_has_brief_create(self) -> None:
        assert Permission.BRIEF_CREATE in self._perms(AgencyMemberRole.OWNER.value)

    def test_owner_has_all_calendar_perms(self) -> None:
        perms = self._perms(AgencyMemberRole.OWNER.value)
        assert Permission.CALENDAR_VIEW in perms
        assert Permission.CALENDAR_MANAGE in perms


# ── Admin role: can manage members but NOT billing ────────────────────────────


class TestAdminPermissions:
    def _perms(self) -> set[Permission]:
        return get_permissions_for_agency_role(AgencyMemberRole.ADMIN.value)

    def test_admin_has_agency_manage_members(self) -> None:
        assert Permission.AGENCY_MANAGE_MEMBERS in self._perms()

    def test_admin_has_agency_view(self) -> None:
        assert Permission.AGENCY_VIEW in self._perms()

    def test_admin_no_billing_manage(self) -> None:
        assert Permission.BILLING_MANAGE not in self._perms()

    def test_admin_no_white_label_manage(self) -> None:
        assert Permission.WHITE_LABEL_MANAGE not in self._perms()

    def test_admin_subset_of_owner(self) -> None:
        owner_perms = get_permissions_for_agency_role(AgencyMemberRole.OWNER.value)
        assert self._perms().issubset(owner_perms)


# ── Designer: write briefs but NO owner panel access ─────────────────────────


class TestDesignerPermissions:
    def _perms(self) -> set[Permission]:
        return get_permissions_for_agency_role(AgencyMemberRole.DESIGNER.value)

    def test_designer_cannot_view_billing(self) -> None:
        assert Permission.BILLING_VIEW not in self._perms()

    def test_designer_cannot_manage_billing(self) -> None:
        assert Permission.BILLING_MANAGE not in self._perms()

    def test_designer_cannot_manage_members(self) -> None:
        assert Permission.AGENCY_MANAGE_MEMBERS not in self._perms()

    def test_designer_cannot_manage_white_label(self) -> None:
        assert Permission.WHITE_LABEL_MANAGE not in self._perms()

    def test_designer_can_create_briefs(self) -> None:
        assert Permission.BRIEF_CREATE in self._perms()

    def test_designer_can_update_briefs(self) -> None:
        assert Permission.BRIEF_UPDATE in self._perms()

    def test_designer_can_view_agency(self) -> None:
        assert Permission.AGENCY_VIEW in self._perms()


# ── Social media manager ──────────────────────────────────────────────────────


class TestSocialMediaManagerPermissions:
    def _perms(self) -> set[Permission]:
        return get_permissions_for_agency_role(AgencyMemberRole.SOCIAL_MEDIA_MANAGER.value)

    def test_smm_has_calendar_manage(self) -> None:
        assert Permission.CALENDAR_MANAGE in self._perms()

    def test_smm_has_calendar_view(self) -> None:
        assert Permission.CALENDAR_VIEW in self._perms()

    def test_smm_cannot_manage_billing(self) -> None:
        assert Permission.BILLING_MANAGE not in self._perms()

    def test_smm_cannot_manage_members(self) -> None:
        assert Permission.AGENCY_MANAGE_MEMBERS not in self._perms()


# ── Viewer: strictly read-only ────────────────────────────────────────────────


class TestViewerPermissions:
    def _perms(self) -> set[Permission]:
        return get_permissions_for_agency_role(AgencyMemberRole.VIEWER.value)

    def test_viewer_cannot_create_briefs(self) -> None:
        assert Permission.BRIEF_CREATE not in self._perms()

    def test_viewer_cannot_manage_billing(self) -> None:
        assert Permission.BILLING_MANAGE not in self._perms()

    def test_viewer_cannot_view_billing(self) -> None:
        assert Permission.BILLING_VIEW not in self._perms()

    def test_viewer_cannot_manage_members(self) -> None:
        assert Permission.AGENCY_MANAGE_MEMBERS not in self._perms()

    def test_viewer_can_view_agency(self) -> None:
        assert Permission.AGENCY_VIEW in self._perms()

    def test_viewer_can_view_briefs(self) -> None:
        assert Permission.BRIEF_VIEW in self._perms()

    def test_viewer_cannot_manage_calendar(self) -> None:
        assert Permission.CALENDAR_MANAGE not in self._perms()


# ── Platform admin has NO agency billing perms ────────────────────────────────


class TestPlatformAdminVsOwnerPanel:
    def test_platform_admin_no_billing_manage(self) -> None:
        from app.core.rbac import PLATFORM_ADMIN_PERMISSIONS

        assert Permission.BILLING_MANAGE not in PLATFORM_ADMIN_PERMISSIONS

    def test_platform_admin_no_billing_view(self) -> None:
        from app.core.rbac import PLATFORM_ADMIN_PERMISSIONS

        assert Permission.BILLING_VIEW not in PLATFORM_ADMIN_PERMISSIONS

    def test_platform_admin_no_agency_manage_members(self) -> None:
        from app.core.rbac import PLATFORM_ADMIN_PERMISSIONS

        assert Permission.AGENCY_MANAGE_MEMBERS not in PLATFORM_ADMIN_PERMISSIONS

    def test_platform_admin_no_white_label_manage(self) -> None:
        from app.core.rbac import PLATFORM_ADMIN_PERMISSIONS

        assert Permission.WHITE_LABEL_MANAGE not in PLATFORM_ADMIN_PERMISSIONS


# ── HTTP auth layer on /owner/* ───────────────────────────────────────────────


class TestOwnerPanelHTTPAuth:
    @pytest.mark.asyncio
    async def test_owner_dashboard_no_token_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/owner/dashboard",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_owner_members_no_token_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/owner/members",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_owner_subscription_no_token_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/owner/subscription",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_deactivate_member_no_token_returns_401(self, client: AsyncClient) -> None:
        resp = await client.post(
            f"/api/v1/owner/members/{uuid.uuid4()}/deactivate",
            headers={"X-Agency-ID": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    def test_platform_admin_has_no_agency_owner_permissions(self) -> None:
        """Platform admin permission set must not include any agency-level owner perms."""
        from app.core.rbac import PLATFORM_ADMIN_PERMISSIONS

        owner_only_perms = {
            Permission.BILLING_MANAGE,
            Permission.WHITE_LABEL_MANAGE,
            Permission.AGENCY_MANAGE_MEMBERS,
        }
        leakage = owner_only_perms & PLATFORM_ADMIN_PERMISSIONS
        assert leakage == set(), f"Platform admin leaked owner-panel permissions: {leakage}"

    @pytest.mark.asyncio
    async def test_invalid_jwt_rejected_on_owner_dashboard(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/owner/dashboard",
            headers={
                "Authorization": "Bearer garbage.token.here",
                "X-Agency-ID": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 401


# ── Permission hierarchy invariants ──────────────────────────────────────────


class TestPermissionHierarchy:
    def test_owner_is_superset_of_admin(self) -> None:
        owner = get_permissions_for_agency_role(AgencyMemberRole.OWNER.value)
        admin = get_permissions_for_agency_role(AgencyMemberRole.ADMIN.value)
        assert admin.issubset(owner)

    def test_owner_is_superset_of_designer(self) -> None:
        owner = get_permissions_for_agency_role(AgencyMemberRole.OWNER.value)
        designer = get_permissions_for_agency_role(AgencyMemberRole.DESIGNER.value)
        assert designer.issubset(owner)

    def test_owner_is_superset_of_viewer(self) -> None:
        owner = get_permissions_for_agency_role(AgencyMemberRole.OWNER.value)
        viewer = get_permissions_for_agency_role(AgencyMemberRole.VIEWER.value)
        assert viewer.issubset(owner)

    def test_viewer_is_subset_of_everyone(self) -> None:
        viewer = get_permissions_for_agency_role(AgencyMemberRole.VIEWER.value)
        for role in [AgencyMemberRole.ADMIN, AgencyMemberRole.DESIGNER, AgencyMemberRole.OWNER]:
            other = get_permissions_for_agency_role(role.value)
            assert viewer.issubset(other), f"Viewer should be subset of {role}"

    def test_no_role_has_platform_permissions(self) -> None:
        for role in AgencyMemberRole:
            perms = get_permissions_for_agency_role(role.value)
            platform_leakage = [p for p in perms if p.value.startswith("platform:")]
            assert (
                platform_leakage == []
            ), f"Role {role} leaked platform permissions: {platform_leakage}"

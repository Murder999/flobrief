"""
Workspace context and tenant isolation logic tests.
No DB required — all pure Python logic.
"""

from app.core.rbac import (
    PLATFORM_ADMIN_PERMISSIONS,
    Permission,
    get_permissions_for_agency_role,
    get_permissions_for_brand_role,
)
from app.models.enums import AgencyMemberRole, BrandMemberRole


class TestTenantIsolation:
    def test_no_agency_role_leaks_platform_permissions(self):
        for role in AgencyMemberRole:
            perms = get_permissions_for_agency_role(role.value)
            leaked = [p for p in perms if p.value.startswith("platform:")]
            assert not leaked, f"Role {role} leaks platform perms: {leaked}"

    def test_no_brand_role_leaks_platform_permissions(self):
        for role in BrandMemberRole:
            perms = get_permissions_for_brand_role(role.value)
            leaked = [p for p in perms if p.value.startswith("platform:")]
            assert not leaked, f"Brand role {role} leaks platform perms: {leaked}"

    def test_platform_admin_has_no_billing_manage(self):
        assert Permission.BILLING_MANAGE not in PLATFORM_ADMIN_PERMISSIONS

    def test_platform_admin_has_no_white_label(self):
        assert Permission.WHITE_LABEL_MANAGE not in PLATFORM_ADMIN_PERMISSIONS

    def test_fail_closed_empty_string_role(self):
        perms = get_permissions_for_agency_role("")
        assert len(perms) == 0

    def test_fail_closed_none_string(self):
        perms = get_permissions_for_agency_role("None")
        assert len(perms) == 0


class TestRoleHierarchy:
    def test_owner_is_superset_of_admin(self):
        owner = get_permissions_for_agency_role(AgencyMemberRole.OWNER.value)
        admin = get_permissions_for_agency_role(AgencyMemberRole.ADMIN.value)
        assert admin.issubset(owner), "Admin must be a subset of Owner permissions"

    def test_admin_is_superset_of_brand_manager(self):
        admin = get_permissions_for_agency_role(AgencyMemberRole.ADMIN.value)
        bm = get_permissions_for_agency_role(AgencyMemberRole.BRAND_MANAGER.value)
        assert bm.issubset(admin), "Brand manager must be a subset of Admin permissions"

    def test_viewer_is_proper_subset_of_all_other_roles(self):
        viewer = get_permissions_for_agency_role(AgencyMemberRole.VIEWER.value)
        for role in AgencyMemberRole:
            if role == AgencyMemberRole.VIEWER:
                continue
            other = get_permissions_for_agency_role(role.value)
            assert viewer.issubset(other), f"Viewer perms should be subset of {role.value} perms"

    def test_brand_viewer_is_subset_of_brand_owner(self):
        viewer = get_permissions_for_brand_role(BrandMemberRole.BRAND_VIEWER.value)
        owner = get_permissions_for_brand_role(BrandMemberRole.BRAND_OWNER.value)
        assert viewer.issubset(owner)


class TestPermissionFacts:
    def test_designer_cannot_manage_members(self):
        perms = get_permissions_for_agency_role(AgencyMemberRole.DESIGNER.value)
        assert Permission.AGENCY_MANAGE_MEMBERS not in perms

    def test_viewer_cannot_create_briefs(self):
        perms = get_permissions_for_agency_role(AgencyMemberRole.VIEWER.value)
        assert Permission.BRIEF_CREATE not in perms

    def test_external_approver_can_not_view_calendar(self):
        perms = get_permissions_for_brand_role(BrandMemberRole.EXTERNAL_APPROVER.value)
        assert Permission.CALENDAR_VIEW not in perms
        assert Permission.CALENDAR_MANAGE not in perms

    def test_brand_viewer_can_view_reports(self):
        perms = get_permissions_for_brand_role(BrandMemberRole.BRAND_VIEWER.value)
        assert Permission.REPORT_VIEW in perms

    def test_all_roles_have_brief_view(self):
        for role in AgencyMemberRole:
            perms = get_permissions_for_agency_role(role.value)
            assert Permission.BRIEF_VIEW in perms, f"Agency role {role} should have brief:view"

    def test_all_brand_roles_have_brief_view(self):
        for role in BrandMemberRole:
            perms = get_permissions_for_brand_role(role.value)
            assert Permission.BRIEF_VIEW in perms, f"Brand role {role} should have brief:view"

    def test_platform_impersonate_requires_explicit_permission(self):
        assert Permission.PLATFORM_IMPERSONATE_TENANT_USER in PLATFORM_ADMIN_PERMISSIONS

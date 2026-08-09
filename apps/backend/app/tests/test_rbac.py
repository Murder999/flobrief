"""
Unit tests for RBAC permission system.
No DB required — all pure Python logic.
"""

from app.core.rbac import (
    PLATFORM_ADMIN_PERMISSIONS,
    Permission,
    get_permissions_for_agency_role,
    get_permissions_for_brand_role,
    get_permissions_for_user_type,
)
from app.models.enums import AgencyMemberRole, BrandMemberRole, UserType


class TestPermissionEnum:
    def test_all_permissions_have_namespace(self):
        for perm in Permission:
            assert ":" in perm.value, f"Permission {perm} missing namespace separator"

    def test_permission_values_unique(self):
        values = [p.value for p in Permission]
        assert len(values) == len(set(values)), "Duplicate permission values found"

    def test_agency_permissions_not_platform(self):
        agency_perms = {
            Permission.AGENCY_VIEW,
            Permission.BRAND_CREATE,
            Permission.BRIEF_VIEW,
            Permission.BILLING_MANAGE,
            Permission.WHITE_LABEL_MANAGE,
        }
        for p in agency_perms:
            assert not p.value.startswith("platform:"), f"{p} should not be platform:"

    def test_platform_permissions_all_start_with_platform(self):
        for p in PLATFORM_ADMIN_PERMISSIONS:
            assert p.value.startswith("platform:"), f"{p} should start with platform:"


class TestAgencyRolePermissions:
    def test_owner_has_all_agency_perms(self):
        perms = get_permissions_for_agency_role(AgencyMemberRole.OWNER.value)
        assert Permission.BILLING_MANAGE in perms
        assert Permission.WHITE_LABEL_MANAGE in perms
        assert Permission.AGENCY_MANAGE_MEMBERS in perms
        assert Permission.BRAND_CREATE in perms
        assert Permission.BRIEF_CREATE in perms

    def test_admin_no_billing_manage_no_white_label(self):
        perms = get_permissions_for_agency_role(AgencyMemberRole.ADMIN.value)
        assert Permission.BILLING_MANAGE not in perms
        assert Permission.WHITE_LABEL_MANAGE not in perms
        assert Permission.AGENCY_MANAGE_MEMBERS in perms

    def test_owner_and_admin_can_manage_whatsapp_notifications(self):
        owner_perms = get_permissions_for_agency_role(AgencyMemberRole.OWNER.value)
        admin_perms = get_permissions_for_agency_role(AgencyMemberRole.ADMIN.value)
        assert Permission.AGENCY_MANAGE_NOTIFICATIONS in owner_perms
        assert Permission.AGENCY_MANAGE_NOTIFICATIONS in admin_perms

    def test_non_admin_roles_cannot_manage_whatsapp_notifications(self):
        for role in (
            AgencyMemberRole.BRAND_MANAGER,
            AgencyMemberRole.DESIGNER,
            AgencyMemberRole.DEVELOPER,
            AgencyMemberRole.SOCIAL_MEDIA_MANAGER,
            AgencyMemberRole.VIEWER,
        ):
            perms = get_permissions_for_agency_role(role.value)
            assert Permission.AGENCY_MANAGE_NOTIFICATIONS not in perms, role

    def test_admin_subset_of_owner(self):
        owner = get_permissions_for_agency_role(AgencyMemberRole.OWNER.value)
        admin = get_permissions_for_agency_role(AgencyMemberRole.ADMIN.value)
        assert admin.issubset(owner)

    def test_designer_cannot_manage_billing(self):
        perms = get_permissions_for_agency_role(AgencyMemberRole.DESIGNER.value)
        assert Permission.BILLING_VIEW not in perms
        assert Permission.BILLING_MANAGE not in perms
        assert Permission.AGENCY_MANAGE_MEMBERS not in perms

    def test_designer_can_write_briefs(self):
        perms = get_permissions_for_agency_role(AgencyMemberRole.DESIGNER.value)
        assert Permission.BRIEF_CREATE in perms
        assert Permission.BRIEF_UPDATE in perms
        assert Permission.BRIEF_VIEW in perms

    def test_social_media_manager_has_calendar_manage(self):
        perms = get_permissions_for_agency_role(AgencyMemberRole.SOCIAL_MEDIA_MANAGER.value)
        assert Permission.CALENDAR_MANAGE in perms
        assert Permission.CALENDAR_VIEW in perms

    def test_viewer_readonly(self):
        perms = get_permissions_for_agency_role(AgencyMemberRole.VIEWER.value)
        assert Permission.BRIEF_CREATE not in perms
        assert Permission.BILLING_VIEW not in perms
        assert Permission.BRIEF_VIEW in perms
        assert Permission.AGENCY_VIEW in perms

    def test_unknown_role_fail_closed(self):
        perms = get_permissions_for_agency_role("injected_evil_role")
        assert len(perms) == 0

    def test_no_agency_role_has_platform_perms(self):
        for role in AgencyMemberRole:
            perms = get_permissions_for_agency_role(role.value)
            for p in perms:
                assert not p.value.startswith(
                    "platform:"
                ), f"Agency role {role} should not have platform permission {p}"


class TestBrandRolePermissions:
    def test_external_approver_can_approve_and_revise(self):
        perms = get_permissions_for_brand_role(BrandMemberRole.EXTERNAL_APPROVER.value)
        assert Permission.BRIEF_APPROVE in perms
        assert Permission.BRIEF_REQUEST_REVISION in perms
        assert Permission.BRIEF_COMMENT in perms
        assert Permission.BRIEF_VIEW in perms

    def test_external_approver_no_billing_no_calendar_manage(self):
        perms = get_permissions_for_brand_role(BrandMemberRole.EXTERNAL_APPROVER.value)
        assert Permission.BILLING_MANAGE not in perms
        assert Permission.CALENDAR_MANAGE not in perms
        assert Permission.CALENDAR_VIEW not in perms

    def test_brand_viewer_readonly(self):
        # brand_viewer merges the spec's "member" (comment-only) and "viewer"
        # tiers: view + comment, but never a final approval decision.
        perms = get_permissions_for_brand_role(BrandMemberRole.BRAND_VIEWER.value)
        assert Permission.BRIEF_APPROVE not in perms
        assert Permission.BRIEF_COMMENT in perms
        assert Permission.BRIEF_VIEW in perms
        assert Permission.BRAND_PORTAL_VIEW in perms

    def test_brand_owner_can_view_calendar(self):
        perms = get_permissions_for_brand_role(BrandMemberRole.BRAND_OWNER.value)
        assert Permission.CALENDAR_VIEW in perms
        assert Permission.REPORT_VIEW in perms

    def test_no_brand_role_has_platform_perms(self):
        for role in BrandMemberRole:
            perms = get_permissions_for_brand_role(role.value)
            for p in perms:
                assert not p.value.startswith("platform:")


class TestPlatformAdminPermissions:
    def test_platform_admin_has_all_platform_perms(self):
        expected = {
            Permission.PLATFORM_ACCESS_ADMIN_PANEL,
            Permission.PLATFORM_VIEW_ALL_TENANTS,
            Permission.PLATFORM_MANAGE_TENANTS,
            Permission.PLATFORM_VIEW_ALL_USERS,
            Permission.PLATFORM_MANAGE_USERS,
            Permission.PLATFORM_VIEW_SUBSCRIPTIONS,
            Permission.PLATFORM_MANAGE_SUBSCRIPTIONS,
            Permission.PLATFORM_VIEW_REVENUE,
            Permission.PLATFORM_VIEW_SYSTEM_AUDIT_LOGS,
            Permission.PLATFORM_IMPERSONATE_TENANT_USER,
            Permission.PLATFORM_RESET_USER_PASSWORD,
            Permission.PLATFORM_SUSPEND_TENANT,
            Permission.PLATFORM_DELETE_TENANT,
            Permission.PLATFORM_VIEW_SYSTEM_HEALTH,
        }
        assert expected.issubset(PLATFORM_ADMIN_PERMISSIONS)

    def test_platform_admin_has_no_billing_manage(self):
        assert Permission.BILLING_MANAGE not in PLATFORM_ADMIN_PERMISSIONS

    def test_platform_admin_has_no_agency_update(self):
        assert Permission.AGENCY_UPDATE not in PLATFORM_ADMIN_PERMISSIONS


class TestGetPermissionsForUserType:
    def test_platform_admin_type_returns_platform_perms(self):
        perms = get_permissions_for_user_type(UserType.PLATFORM_ADMIN.value)
        assert Permission.PLATFORM_ACCESS_ADMIN_PANEL in perms

    def test_agency_user_with_owner_role(self):
        perms = get_permissions_for_user_type(
            UserType.AGENCY_USER.value, AgencyMemberRole.OWNER.value
        )
        assert Permission.BILLING_MANAGE in perms

    def test_brand_user_with_external_approver_role(self):
        perms = get_permissions_for_user_type(
            UserType.BRAND_USER.value, BrandMemberRole.EXTERNAL_APPROVER.value
        )
        assert Permission.BRIEF_APPROVE in perms

    def test_no_role_returns_empty(self):
        perms = get_permissions_for_user_type(UserType.AGENCY_USER.value, None)
        assert len(perms) == 0

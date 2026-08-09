from __future__ import annotations

from enum import StrEnum

from app.models.enums import AgencyMemberRole, BrandMemberRole, UserType


class Permission(StrEnum):
    # Agency-scoped permissions
    AGENCY_VIEW = "agency:view"
    AGENCY_UPDATE = "agency:update"
    AGENCY_MANAGE_MEMBERS = "agency:manage_members"
    AGENCY_MANAGE_NOTIFICATIONS = "agency:manage_notifications"
    BRAND_CREATE = "brand:create"
    BRAND_VIEW = "brand:view"
    BRAND_UPDATE = "brand:update"
    BRAND_ARCHIVE = "brand:archive"
    BRIEF_CREATE = "brief:create"
    BRIEF_VIEW = "brief:view"
    BRIEF_UPDATE = "brief:update"
    BRIEF_SUBMIT_APPROVAL = "brief:submit_approval"
    CALENDAR_VIEW = "calendar:view"
    CALENDAR_MANAGE = "calendar:manage"
    REPORTING_VIEW = "reporting:view"
    BILLING_VIEW = "billing:view"
    BILLING_MANAGE = "billing:manage"
    WHITE_LABEL_MANAGE = "white_label:manage"

    # Template permissions
    TEMPLATE_VIEW = "template:view"
    TEMPLATE_CREATE = "template:create"
    TEMPLATE_UPDATE = "template:update"
    TEMPLATE_ARCHIVE = "template:archive"

    # Brand-portal permissions (brand member context)
    BRAND_PORTAL_VIEW = "brand_portal:view"
    BRIEF_COMMENT = "brief:comment"
    BRIEF_APPROVE = "brief:approve"
    BRIEF_REQUEST_REVISION = "brief:request_revision"
    REPORT_VIEW = "report:view"

    # Platform admin permissions
    PLATFORM_ACCESS_ADMIN_PANEL = "platform:access_admin_panel"
    PLATFORM_VIEW_ALL_TENANTS = "platform:view_all_tenants"
    PLATFORM_MANAGE_TENANTS = "platform:manage_tenants"
    PLATFORM_VIEW_ALL_USERS = "platform:view_all_users"
    PLATFORM_MANAGE_USERS = "platform:manage_users"
    PLATFORM_VIEW_SUBSCRIPTIONS = "platform:view_subscriptions"
    PLATFORM_MANAGE_SUBSCRIPTIONS = "platform:manage_subscriptions"
    PLATFORM_VIEW_REVENUE = "platform:view_revenue"
    PLATFORM_VIEW_SYSTEM_AUDIT_LOGS = "platform:view_system_audit_logs"
    PLATFORM_IMPERSONATE_TENANT_USER = "platform:impersonate_tenant_user"
    PLATFORM_RESET_USER_PASSWORD = "platform:reset_user_password"
    PLATFORM_SUSPEND_TENANT = "platform:suspend_tenant"
    PLATFORM_DELETE_TENANT = "platform:delete_tenant"
    PLATFORM_VIEW_SYSTEM_HEALTH = "platform:view_system_health"

    # Time tracking permissions
    TIME_ENTRY_LOG = "time_entry:log"
    TIME_ENTRY_VIEW_TEAM = "time_entry:view_team"
    TIME_ENTRY_APPROVE = "time_entry:approve"
    TIME_ENTRY_MANAGE = "time_entry:manage"

    # Capacity/resource-planning permissions
    CAPACITY_VIEW_OWN = "capacity:view_own"
    CAPACITY_VIEW_TEAM = "capacity:view_team"
    CAPACITY_MANAGE_SCHEDULE = "capacity:manage_schedule"
    CAPACITY_MANAGE_ALLOCATION = "capacity:manage_allocation"
    TIME_OFF_REQUEST = "time_off:request"
    TIME_OFF_APPROVE = "time_off:approve"

    # Finance permissions (commercial terms + internal cost rates)
    COMMERCIAL_TERMS_VIEW = "commercial_terms:view"
    COMMERCIAL_TERMS_MANAGE = "commercial_terms:manage"
    COST_RATE_VIEW = "cost_rate:view"
    COST_RATE_MANAGE = "cost_rate:manage"

    # Invoicing permissions (plan §8, Phase 4)
    BILLING_TIME_VIEW = "billing_time:view"
    INVOICE_VIEW = "invoice:view"
    INVOICE_CREATE = "invoice:create"
    INVOICE_APPROVE = "invoice:approve"
    INVOICE_VOID = "invoice:void"

    # Accounting connector + payments permissions (plan §8, Phase 5)
    PAYMENT_VIEW = "payment:view"
    PAYMENT_MANAGE = "payment:manage"
    ACCOUNTING_INTEGRATION_MANAGE = "accounting_integration:manage"

    # Profitability analytics permission (plan §8, Phase 6)
    PROFITABILITY_VIEW = "profitability:view"


_P = Permission

# All agency-level permissions (shared subset)
_AGENCY_BASE = frozenset(
    {
        _P.AGENCY_VIEW,
        _P.BRAND_VIEW,
        _P.BRIEF_VIEW,
        _P.CALENDAR_VIEW,
        _P.TEMPLATE_VIEW,
        _P.BRIEF_COMMENT,
    }
)

_AGENCY_WRITER = _AGENCY_BASE | frozenset(
    {
        _P.BRIEF_CREATE,
        _P.BRIEF_UPDATE,
        _P.BRIEF_SUBMIT_APPROVAL,
    }
)

_AGENCY_FULL = _AGENCY_WRITER | frozenset(
    {
        _P.AGENCY_UPDATE,
        _P.AGENCY_MANAGE_MEMBERS,
        _P.AGENCY_MANAGE_NOTIFICATIONS,
        _P.BRAND_CREATE,
        _P.BRAND_UPDATE,
        _P.BRAND_ARCHIVE,
        _P.CALENDAR_MANAGE,
        _P.REPORTING_VIEW,
        _P.BILLING_VIEW,
        _P.BILLING_MANAGE,
        _P.WHITE_LABEL_MANAGE,
        _P.BRAND_PORTAL_VIEW,
        _P.TEMPLATE_CREATE,
        _P.TEMPLATE_UPDATE,
        _P.TEMPLATE_ARCHIVE,
        _P.TIME_ENTRY_LOG,
        _P.TIME_ENTRY_VIEW_TEAM,
        _P.TIME_ENTRY_APPROVE,
        _P.TIME_ENTRY_MANAGE,
        _P.CAPACITY_VIEW_OWN,
        _P.CAPACITY_VIEW_TEAM,
        _P.CAPACITY_MANAGE_SCHEDULE,
        _P.CAPACITY_MANAGE_ALLOCATION,
        _P.TIME_OFF_REQUEST,
        _P.TIME_OFF_APPROVE,
        _P.COMMERCIAL_TERMS_VIEW,
        _P.COMMERCIAL_TERMS_MANAGE,
        _P.COST_RATE_VIEW,
        _P.COST_RATE_MANAGE,
        _P.BILLING_TIME_VIEW,
        _P.INVOICE_VIEW,
        _P.INVOICE_CREATE,
        _P.INVOICE_APPROVE,
        _P.INVOICE_VOID,
        _P.PAYMENT_VIEW,
        _P.PAYMENT_MANAGE,
        _P.ACCOUNTING_INTEGRATION_MANAGE,
        _P.PROFITABILITY_VIEW,
    }
)

_AGENCY_ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    AgencyMemberRole.OWNER.value: _AGENCY_FULL,
    # Admin: everything except BILLING_MANAGE/WHITE_LABEL_MANAGE (existing
    # exclusions), COST_RATE_VIEW/COST_RATE_MANAGE, and
    # ACCOUNTING_INTEGRATION_MANAGE — conservative default per plan §8; each
    # stays Owner-only until product policy widens it. Admin keeps
    # PAYMENT_VIEW/PAYMENT_MANAGE.
    AgencyMemberRole.ADMIN.value: _AGENCY_FULL
    - frozenset(
        {
            _P.BILLING_MANAGE,
            _P.WHITE_LABEL_MANAGE,
            _P.COST_RATE_VIEW,
            _P.COST_RATE_MANAGE,
            _P.ACCOUNTING_INTEGRATION_MANAGE,
        }
    ),
    AgencyMemberRole.BRAND_MANAGER.value: _AGENCY_WRITER
    | frozenset(
        {
            _P.BRAND_CREATE,
            _P.BRAND_UPDATE,
            _P.BRAND_ARCHIVE,
            _P.CALENDAR_MANAGE,
            _P.REPORTING_VIEW,
            _P.BILLING_VIEW,
            _P.TEMPLATE_CREATE,
            _P.TEMPLATE_UPDATE,
            _P.TIME_ENTRY_LOG,
            _P.TIME_ENTRY_VIEW_TEAM,
            _P.CAPACITY_VIEW_OWN,
            _P.CAPACITY_VIEW_TEAM,
            _P.COMMERCIAL_TERMS_VIEW,
            _P.BILLING_TIME_VIEW,
            _P.INVOICE_VIEW,
            _P.PROFITABILITY_VIEW,
        }
    ),
    AgencyMemberRole.DESIGNER.value: _AGENCY_BASE
    | frozenset(
        {
            _P.BRIEF_CREATE,
            _P.BRIEF_UPDATE,
            _P.TIME_ENTRY_LOG,
            _P.CAPACITY_VIEW_OWN,
            _P.TIME_OFF_REQUEST,
        }
    ),
    AgencyMemberRole.DEVELOPER.value: _AGENCY_BASE
    | frozenset(
        {
            _P.TIME_ENTRY_LOG,
            _P.CAPACITY_VIEW_OWN,
            _P.TIME_OFF_REQUEST,
        }
    ),
    AgencyMemberRole.SOCIAL_MEDIA_MANAGER.value: _AGENCY_BASE
    | frozenset(
        {
            _P.BRIEF_CREATE,
            _P.CALENDAR_MANAGE,
            _P.REPORTING_VIEW,
            _P.TIME_ENTRY_LOG,
            _P.CAPACITY_VIEW_OWN,
            _P.TIME_OFF_REQUEST,
        }
    ),
    AgencyMemberRole.VIEWER.value: _AGENCY_BASE | frozenset({_P.CAPACITY_VIEW_OWN}),
}

_BRAND_ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    BrandMemberRole.BRAND_OWNER.value: frozenset(
        {
            _P.BRAND_PORTAL_VIEW,
            _P.BRIEF_VIEW,
            _P.BRIEF_COMMENT,
            _P.BRIEF_APPROVE,
            _P.BRIEF_REQUEST_REVISION,
            _P.CALENDAR_VIEW,
            _P.REPORT_VIEW,
        }
    ),
    BrandMemberRole.BRAND_MANAGER.value: frozenset(
        {
            _P.BRAND_PORTAL_VIEW,
            _P.BRIEF_VIEW,
            _P.BRIEF_COMMENT,
            _P.BRIEF_APPROVE,
            _P.BRIEF_REQUEST_REVISION,
            _P.CALENDAR_VIEW,
            _P.REPORT_VIEW,
        }
    ),
    BrandMemberRole.BRAND_VIEWER.value: frozenset(
        {
            _P.BRAND_PORTAL_VIEW,
            _P.BRIEF_VIEW,
            _P.BRIEF_COMMENT,
            _P.CALENDAR_VIEW,
            _P.REPORT_VIEW,
        }
    ),
    BrandMemberRole.EXTERNAL_APPROVER.value: frozenset(
        {
            _P.BRIEF_VIEW,
            _P.BRIEF_COMMENT,
            _P.BRIEF_APPROVE,
            _P.BRIEF_REQUEST_REVISION,
        }
    ),
}

PLATFORM_ADMIN_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        _P.PLATFORM_ACCESS_ADMIN_PANEL,
        _P.PLATFORM_VIEW_ALL_TENANTS,
        _P.PLATFORM_MANAGE_TENANTS,
        _P.PLATFORM_VIEW_ALL_USERS,
        _P.PLATFORM_MANAGE_USERS,
        _P.PLATFORM_VIEW_SUBSCRIPTIONS,
        _P.PLATFORM_MANAGE_SUBSCRIPTIONS,
        _P.PLATFORM_VIEW_REVENUE,
        _P.PLATFORM_VIEW_SYSTEM_AUDIT_LOGS,
        _P.PLATFORM_IMPERSONATE_TENANT_USER,
        _P.PLATFORM_RESET_USER_PASSWORD,
        _P.PLATFORM_SUSPEND_TENANT,
        _P.PLATFORM_DELETE_TENANT,
        _P.PLATFORM_VIEW_SYSTEM_HEALTH,
    }
)


def get_permissions_for_agency_role(role: str) -> frozenset[Permission]:
    """Return permissions for an agency member role. Fail-closed: unknown → empty."""
    return _AGENCY_ROLE_PERMISSIONS.get(role, frozenset())


def get_permissions_for_brand_role(role: str) -> frozenset[Permission]:
    """Return permissions for a brand member role. Fail-closed: unknown → empty."""
    return _BRAND_ROLE_PERMISSIONS.get(role, frozenset())


def get_permissions_for_user_type(user_type: str, role: str | None = None) -> frozenset[Permission]:
    """Resolve permissions based on user_type and optional role."""
    if user_type == UserType.PLATFORM_ADMIN.value:
        return PLATFORM_ADMIN_PERMISSIONS
    if user_type == UserType.AGENCY_USER.value and role:
        return get_permissions_for_agency_role(role)
    if user_type == UserType.BRAND_USER.value and role:
        return get_permissions_for_brand_role(role)
    return frozenset()

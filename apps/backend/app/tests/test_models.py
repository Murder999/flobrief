"""Unit tests for ORM model structure and enum integrity."""

from app.models.agency_member import AgencyMember
from app.models.brand_member import BrandMember
from app.models.enums import (
    AgencyMemberRole,
    AgencyMemberStatus,
    BillingProvider,
    BrandMemberRole,
    BrandMemberStatus,
    PlanCode,
    SubscriptionStatus,
    UserType,
)
from app.models.platform_audit_log import PlatformAuditLog
from app.models.subscription import Subscription
from app.models.user import User


def _column_names(model: type) -> set[str]:
    return {col.key for col in model.__table__.columns}


class TestUserType:
    def test_has_platform_admin(self) -> None:
        assert UserType.PLATFORM_ADMIN.value == "platform_admin"

    def test_has_agency_user(self) -> None:
        assert UserType.AGENCY_USER.value == "agency_user"

    def test_has_brand_user(self) -> None:
        assert UserType.BRAND_USER.value == "brand_user"

    def test_exactly_three_types(self) -> None:
        assert len(UserType) == 3


class TestUserModel:
    def test_no_agency_id_column(self) -> None:
        assert "agency_id" not in _column_names(User)

    def test_no_brand_id_column(self) -> None:
        assert "brand_id" not in _column_names(User)

    def test_has_user_type_column(self) -> None:
        assert "user_type" in _column_names(User)

    def test_has_mfa_columns(self) -> None:
        cols = _column_names(User)
        assert "mfa_enabled" in cols
        assert "mfa_secret_encrypted" in cols

    def test_has_soft_delete(self) -> None:
        assert "deleted_at" in _column_names(User)

    def test_is_platform_admin_property(self) -> None:
        user = User(user_type=UserType.PLATFORM_ADMIN.value)
        assert user.is_platform_admin is True

    def test_is_not_platform_admin(self) -> None:
        user = User(user_type=UserType.AGENCY_USER.value)
        assert user.is_platform_admin is False


class TestAgencyMemberConstraints:
    def test_unique_constraint_exists(self) -> None:
        constraint_names = {c.name for c in AgencyMember.__table__.constraints}
        assert "uq_agency_member_agency_user" in constraint_names

    def test_has_role_column(self) -> None:
        assert "role" in _column_names(AgencyMember)

    def test_valid_roles(self) -> None:
        roles = {r.value for r in AgencyMemberRole}
        assert "owner" in roles
        assert "admin" in roles
        assert "viewer" in roles


class TestBrandMemberConstraints:
    def test_unique_constraint_exists(self) -> None:
        constraint_names = {c.name for c in BrandMember.__table__.constraints}
        assert "uq_brand_member_brand_user" in constraint_names

    def test_valid_roles(self) -> None:
        roles = {r.value for r in BrandMemberRole}
        assert "brand_owner" in roles
        assert "external_approver" in roles


class TestSubscriptionConstraint:
    def test_check_constraint_exists(self) -> None:
        constraint_names = {
            c.name for c in Subscription.__table__.constraints if hasattr(c, "name") and c.name
        }
        assert "ck_subscription_exactly_one_tenant" in constraint_names

    def test_has_billing_provider_column(self) -> None:
        assert "billing_provider" in _column_names(Subscription)

    def test_billing_providers(self) -> None:
        assert BillingProvider.MANUAL.value == "manual"
        assert BillingProvider.IYZICO.value == "iyzico"

    def test_subscription_statuses(self) -> None:
        values = {s.value for s in SubscriptionStatus}
        assert "trialing" in values
        assert "past_due" in values
        assert "expired" in values


class TestPlatformAuditLog:
    def test_no_updated_at(self) -> None:
        assert "updated_at" not in _column_names(PlatformAuditLog)

    def test_no_deleted_at(self) -> None:
        assert "deleted_at" not in _column_names(PlatformAuditLog)

    def test_has_created_at(self) -> None:
        assert "created_at" in _column_names(PlatformAuditLog)

    def test_has_admin_user_id(self) -> None:
        assert "admin_user_id" in _column_names(PlatformAuditLog)

    def test_has_meta_column(self) -> None:
        assert "meta" in _column_names(PlatformAuditLog)


class TestPlanCodes:
    def test_all_five_codes_present(self) -> None:
        codes = {c.value for c in PlanCode}
        assert codes == {
            "starter_agency",
            "pro_agency",
            "agency_plus",
            "brand_solo",
            "enterprise",
        }


class TestMemberStatuses:
    def test_agency_member_statuses(self) -> None:
        values = {s.value for s in AgencyMemberStatus}
        assert "active" in values
        assert "invited" in values
        assert "suspended" in values

    def test_brand_member_statuses(self) -> None:
        values = {s.value for s in BrandMemberStatus}
        assert "active" in values
        assert "invited" in values

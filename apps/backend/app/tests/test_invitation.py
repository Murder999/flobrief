"""
Invitation schema and business logic tests.
No DB required — pure schema validation tests.
"""

import pytest
from pydantic import ValidationError

from app.models.enums import AgencyMemberRole, BrandMemberRole
from app.schemas.invitation import AgencyInviteRequest, BrandInviteRequest


class TestAgencyInviteRequest:
    def test_valid_agency_invite_normalizes_email(self):
        req = AgencyInviteRequest(email="Test@Example.COM", role="admin")
        assert req.email == "test@example.com"

    def test_all_valid_agency_roles_accepted(self):
        for role in AgencyMemberRole:
            req = AgencyInviteRequest(email="user@test.com", role=role.value)
            assert req.role == role.value

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            AgencyInviteRequest(email="x@x.com", role="super_admin")

    def test_platform_admin_role_blocked(self):
        with pytest.raises(ValidationError):
            AgencyInviteRequest(email="x@x.com", role="platform_admin")

    def test_brand_role_rejected_for_agency_invite(self):
        with pytest.raises(ValidationError):
            AgencyInviteRequest(email="x@x.com", role="brand_owner")

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            AgencyInviteRequest(email="not-an-email", role="admin")

    def test_optional_message(self):
        req = AgencyInviteRequest(email="x@x.com", role="admin", message="Welcome!")
        assert req.message == "Welcome!"

    def test_no_message_defaults_none(self):
        req = AgencyInviteRequest(email="x@x.com", role="admin")
        assert req.message is None

    def test_message_max_500_chars(self):
        with pytest.raises(ValidationError):
            AgencyInviteRequest(email="x@x.com", role="admin", message="x" * 501)

    def test_email_with_whitespace_stripped(self):
        req = AgencyInviteRequest(email="  user@test.com  ", role="viewer")
        assert req.email == "user@test.com"


class TestBrandInviteRequest:
    def test_valid_brand_invite_normalizes_email(self):
        req = BrandInviteRequest(email="Brand@User.COM", role="brand_viewer")
        assert req.email == "brand@user.com"

    def test_all_valid_brand_roles_accepted(self):
        for role in BrandMemberRole:
            req = BrandInviteRequest(email="x@x.com", role=role.value)
            assert req.role == role.value

    def test_platform_admin_role_blocked(self):
        with pytest.raises(ValidationError):
            BrandInviteRequest(email="x@x.com", role="platform_admin")

    def test_agency_role_rejected_for_brand_invite(self):
        with pytest.raises(ValidationError):
            BrandInviteRequest(email="x@x.com", role="admin")

    def test_invalid_brand_role_rejected(self):
        with pytest.raises(ValidationError):
            BrandInviteRequest(email="x@x.com", role="nonexistent_role")

    def test_external_approver_accepted(self):
        req = BrandInviteRequest(email="approver@brand.com", role="external_approver")
        assert req.role == "external_approver"


class TestInvitationRoleConstraints:
    def test_owner_role_can_be_invited_via_agency(self):
        req = AgencyInviteRequest(email="x@x.com", role=AgencyMemberRole.OWNER.value)
        assert req.role == AgencyMemberRole.OWNER.value

    def test_brand_manager_is_valid_brand_role(self):
        req = BrandInviteRequest(email="x@x.com", role=BrandMemberRole.BRAND_MANAGER.value)
        assert req.role == BrandMemberRole.BRAND_MANAGER.value

    def test_agency_and_brand_invite_use_separate_validators(self):
        # brand_manager exists in both role sets (different context, same name)
        # The invite schemas validate against their respective role enums
        from pydantic import ValidationError

        # brand_owner is only valid for brand invites, not agency
        with pytest.raises(ValidationError):
            AgencyInviteRequest(email="x@x.com", role="brand_owner")
        # viewer is only valid for agency invites, not brand
        with pytest.raises(ValidationError):
            BrandInviteRequest(email="x@x.com", role="viewer")

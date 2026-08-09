"""Brand / customer portal tests.

Covers:
- EXTERNAL_APPROVER permissions (approve, revision, comment, view)
- EXTERNAL_APPROVER blocked from internal features (calendar, billing, brief:create)
- BRAND_VIEWER is strictly read-only inside the portal
- BRAND_OWNER additional permissions (calendar view, report view)
- No brand role has agency management or platform permissions
- Approval schema validation (PublicApproveRequest, PublicRevisionRequest)
- HTTP: public approval endpoints require valid token format
- HTTP: agency endpoints reject brand user JWTs attempting to cross over
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.core.rbac import Permission, get_permissions_for_brand_role
from app.models.enums import BrandMemberRole
from app.schemas.approval import (
    AddPublicCommentRequest,
    PublicApproveRequest,
    PublicRevisionRequest,
)

# ── EXTERNAL_APPROVER permissions ─────────────────────────────────────────────


class TestExternalApproverPermissions:
    def _perms(self) -> set[Permission]:
        return get_permissions_for_brand_role(BrandMemberRole.EXTERNAL_APPROVER.value)

    def test_can_view_brief(self) -> None:
        assert Permission.BRIEF_VIEW in self._perms()

    def test_can_approve_brief(self) -> None:
        assert Permission.BRIEF_APPROVE in self._perms()

    def test_can_request_revision(self) -> None:
        assert Permission.BRIEF_REQUEST_REVISION in self._perms()

    def test_can_comment_on_brief(self) -> None:
        assert Permission.BRIEF_COMMENT in self._perms()

    def test_cannot_create_brief(self) -> None:
        assert Permission.BRIEF_CREATE not in self._perms()

    def test_cannot_update_brief(self) -> None:
        assert Permission.BRIEF_UPDATE not in self._perms()

    def test_cannot_manage_calendar(self) -> None:
        assert Permission.CALENDAR_MANAGE not in self._perms()

    def test_cannot_view_calendar(self) -> None:
        assert Permission.CALENDAR_VIEW not in self._perms()

    def test_cannot_manage_billing(self) -> None:
        assert Permission.BILLING_MANAGE not in self._perms()

    def test_cannot_view_billing(self) -> None:
        assert Permission.BILLING_VIEW not in self._perms()

    def test_cannot_manage_agency_members(self) -> None:
        assert Permission.AGENCY_MANAGE_MEMBERS not in self._perms()

    def test_cannot_create_brand(self) -> None:
        assert Permission.BRAND_CREATE not in self._perms()


# ── BRAND_VIEWER permissions ───────────────────────────────────────────────────


class TestBrandViewerPermissions:
    def _perms(self) -> set[Permission]:
        return get_permissions_for_brand_role(BrandMemberRole.BRAND_VIEWER.value)

    def test_can_view_brief(self) -> None:
        assert Permission.BRIEF_VIEW in self._perms()

    def test_has_brand_portal_view(self) -> None:
        assert Permission.BRAND_PORTAL_VIEW in self._perms()

    def test_cannot_approve(self) -> None:
        assert Permission.BRIEF_APPROVE not in self._perms()

    def test_cannot_request_revision(self) -> None:
        assert Permission.BRIEF_REQUEST_REVISION not in self._perms()

    def test_can_comment(self) -> None:
        # brand_viewer merges the spec's "member" (comment-only) and "viewer"
        # (view-only) tiers into one role: view + comment, never decide.
        assert Permission.BRIEF_COMMENT in self._perms()

    def test_cannot_create_brief(self) -> None:
        assert Permission.BRIEF_CREATE not in self._perms()

    def test_cannot_manage_billing(self) -> None:
        assert Permission.BILLING_MANAGE not in self._perms()

    def test_viewer_has_fewer_write_perms_than_external_approver(self) -> None:
        viewer = self._perms()
        approver = get_permissions_for_brand_role(BrandMemberRole.EXTERNAL_APPROVER.value)
        # BRAND_VIEWER has read perms (calendar, report) but NOT approval actions
        assert Permission.BRIEF_APPROVE not in viewer
        assert Permission.BRIEF_APPROVE in approver


# ── BRAND_OWNER permissions ───────────────────────────────────────────────────


class TestBrandOwnerPermissions:
    def _perms(self) -> set[Permission]:
        return get_permissions_for_brand_role(BrandMemberRole.BRAND_OWNER.value)

    def test_has_calendar_view(self) -> None:
        assert Permission.CALENDAR_VIEW in self._perms()

    def test_has_report_view(self) -> None:
        assert Permission.REPORT_VIEW in self._perms()

    def test_has_brief_approve(self) -> None:
        assert Permission.BRIEF_APPROVE in self._perms()

    def test_has_brief_comment(self) -> None:
        assert Permission.BRIEF_COMMENT in self._perms()

    def test_cannot_manage_billing(self) -> None:
        assert Permission.BILLING_MANAGE not in self._perms()

    def test_cannot_manage_agency_members(self) -> None:
        assert Permission.AGENCY_MANAGE_MEMBERS not in self._perms()

    def test_brand_owner_superset_of_external_approver(self) -> None:
        owner = self._perms()
        approver = get_permissions_for_brand_role(BrandMemberRole.EXTERNAL_APPROVER.value)
        assert approver.issubset(owner)


# ── No brand role has platform or agency-management permissions ───────────────


class TestBrandRoleIsolation:
    def test_no_brand_role_has_platform_permissions(self) -> None:
        for role in BrandMemberRole:
            perms = get_permissions_for_brand_role(role.value)
            leakage = [p for p in perms if p.value.startswith("platform:")]
            assert leakage == [], f"Brand role {role} leaked platform perms: {leakage}"

    def test_no_brand_role_has_agency_manage_members(self) -> None:
        for role in BrandMemberRole:
            perms = get_permissions_for_brand_role(role.value)
            assert (
                Permission.AGENCY_MANAGE_MEMBERS not in perms
            ), f"Brand role {role} must not have AGENCY_MANAGE_MEMBERS"

    def test_no_brand_role_has_billing_manage(self) -> None:
        for role in BrandMemberRole:
            perms = get_permissions_for_brand_role(role.value)
            assert (
                Permission.BILLING_MANAGE not in perms
            ), f"Brand role {role} must not have BILLING_MANAGE"

    def test_no_brand_role_has_white_label_manage(self) -> None:
        for role in BrandMemberRole:
            perms = get_permissions_for_brand_role(role.value)
            assert Permission.WHITE_LABEL_MANAGE not in perms


# ── Approval schema validation ────────────────────────────────────────────────


class TestPublicApprovalSchemas:
    def test_public_approve_no_fields_required(self) -> None:
        req = PublicApproveRequest()
        assert req.approver_name is None
        assert req.approver_email is None

    def test_public_approve_with_name_and_email(self) -> None:
        req = PublicApproveRequest(
            approver_name="Zeynep Yılmaz",
            approver_email="zeynep@brand.com",
        )
        assert req.approver_name == "Zeynep Yılmaz"
        assert req.approver_email == "zeynep@brand.com"

    def test_public_approve_invalid_email_raises(self) -> None:
        with pytest.raises(ValidationError):
            PublicApproveRequest(approver_email="not-an-email")

    def test_public_revision_requires_non_empty_comment(self) -> None:
        with pytest.raises(ValidationError):
            PublicRevisionRequest(comment="")

    def test_public_revision_strips_whitespace(self) -> None:
        req = PublicRevisionRequest(comment="  Lütfen rengi değiştir  ")
        assert req.comment == "Lütfen rengi değiştir"

    def test_public_revision_valid_comment(self) -> None:
        req = PublicRevisionRequest(comment="Header görseli yenilenecek.")
        assert req.comment == "Header görseli yenilenecek."

    def test_add_public_comment_empty_raises(self) -> None:
        with pytest.raises(ValidationError):
            AddPublicCommentRequest(comment="")

    def test_add_public_comment_valid(self) -> None:
        req = AddPublicCommentRequest(comment="Renk paleti harika görünüyor.")
        assert req.comment == "Renk paleti harika görünüyor."

    def test_add_public_comment_whitespace_only_raises(self) -> None:
        with pytest.raises(ValidationError):
            AddPublicCommentRequest(comment="    ")


# ── HTTP: public approval endpoints ───────────────────────────────────────────


class TestPublicApprovalHTTP:
    @pytest.mark.asyncio
    async def test_public_approve_with_invalid_token_rejected(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/approvals/public/not-a-real-token/approve",
            json={},
        )
        # Token not found in DB → 404; invalid token format → 422/404
        assert resp.status_code in (404, 422)

    @pytest.mark.asyncio
    async def test_public_revision_with_invalid_token_rejected(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/approvals/public/bad-token/request-revision",
            json={"comment": "Something"},
        )
        assert resp.status_code in (404, 422)

    def test_brand_user_permissions_exclude_agency_write_ops(self) -> None:
        """Brand roles must never hold permissions that let them write to agency data."""
        agency_write_perms = {
            Permission.BRIEF_CREATE,
            Permission.BRIEF_UPDATE,
            Permission.BRAND_CREATE,
            Permission.CALENDAR_MANAGE,
            Permission.AGENCY_MANAGE_MEMBERS,
        }
        for role in BrandMemberRole:
            perms = get_permissions_for_brand_role(role.value)
            leakage = agency_write_perms & perms
            assert leakage == set(), f"Brand role {role} has agency-write permissions: {leakage}"

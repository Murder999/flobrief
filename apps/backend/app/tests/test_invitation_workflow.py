"""Tests for invitation workflow: rejected status, email matching, brief participant roles."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import AgencyMemberRole, BriefParticipantRole
from app.schemas.brief import BriefParticipantCreate, default_caps_for_role
from app.schemas.invitation import InvitationRead


class TestInvitationSchemas:
    def test_invitation_rejected_at_schema(self) -> None:
        """InvitationRead schema has rejected_at field."""
        fields = InvitationRead.model_fields
        assert "rejected_at" in fields, "InvitationRead must have rejected_at field"

    def test_invitation_read_includes_is_pending(self) -> None:
        """InvitationRead schema has is_pending computed field."""
        fields = InvitationRead.model_fields
        assert "is_pending" in fields


class _FakeInvite:
    """Lightweight stand-in for Invitation to test property logic without SQLAlchemy."""

    def __init__(
        self,
        *,
        accepted_at: datetime | None = None,
        revoked_at: datetime | None = None,
        rejected_at: datetime | None = None,
        deleted_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        self.accepted_at = accepted_at
        self.revoked_at = revoked_at
        self.rejected_at = rejected_at
        self.deleted_at = deleted_at
        self.expires_at = expires_at or (datetime.now(UTC) + timedelta(days=7))

    @property
    def is_pending(self) -> bool:
        now = datetime.now(UTC)
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.rejected_at is None
            and self.deleted_at is None
            and self.expires_at > now
        )

    @property
    def is_accepted(self) -> bool:
        return self.accepted_at is not None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_rejected(self) -> bool:
        return self.rejected_at is not None


class TestInvitationModel:
    def test_expired_invitation_is_not_pending(self) -> None:
        """is_pending returns False when expires_at is in the past."""
        invite = _FakeInvite(expires_at=datetime.now(UTC) - timedelta(hours=1))
        assert invite.is_pending is False

    def test_revoked_invitation_is_not_pending(self) -> None:
        """is_pending returns False when revoked_at is set."""
        invite = _FakeInvite(revoked_at=datetime.now(UTC))
        assert invite.is_pending is False

    def test_rejected_invitation_is_rejected(self) -> None:
        """is_rejected returns True when rejected_at is set."""
        invite = _FakeInvite(rejected_at=datetime.now(UTC))
        assert invite.is_rejected is True
        assert invite.is_pending is False

    def test_pending_invitation_is_pending(self) -> None:
        """is_pending returns True when all conditions are met."""
        invite = _FakeInvite()
        assert invite.is_pending is True


class TestBriefParticipantRole:
    def test_brief_participant_role_enum_values(self) -> None:
        """BriefParticipantRole enum has expected values."""
        role_values = {r.value for r in BriefParticipantRole}
        assert "brand_manager" in role_values
        assert "task_owner" in role_values
        assert "designer" in role_values
        assert "social_media_manager" in role_values
        assert "developer" in role_values
        assert "brand_representative" in role_values
        assert "external_approver" in role_values
        assert "viewer" in role_values

    def test_brief_participant_default_caps_task_owner(self) -> None:
        """default_caps_for_role returns correct caps for task_owner."""
        caps = default_caps_for_role("task_owner")
        assert caps["can_edit"] is True
        assert caps["can_approve"] is True
        assert caps["can_comment"] is True

    def test_brief_participant_default_caps_viewer(self) -> None:
        """default_caps_for_role returns restrictive caps for viewer."""
        caps = default_caps_for_role("viewer")
        assert caps["can_comment"] is False
        assert caps["can_upload"] is False
        assert caps["can_edit"] is False
        assert caps["can_approve"] is False

    def test_brief_participant_default_caps_designer(self) -> None:
        """default_caps_for_role returns editing cap for designer."""
        caps = default_caps_for_role("designer")
        assert caps["can_edit"] is True
        assert caps["can_approve"] is False

    def test_brief_participant_default_caps_external_approver(self) -> None:
        """external_approver gets approve but no upload."""
        caps = default_caps_for_role("external_approver")
        assert caps["can_approve"] is True
        assert caps["can_upload"] is False
        assert caps["can_comment"] is True

    def test_brief_participant_schema_validation(self) -> None:
        """BriefParticipantCreate accepts valid data."""
        import uuid

        data = BriefParticipantCreate(
            user_id=uuid.uuid4(),
            participant_role="designer",
        )
        assert data.participant_role == "designer"
        assert data.can_comment is True

    def test_brief_participant_schema_defaults(self) -> None:
        """BriefParticipantCreate has correct defaults."""
        import uuid

        data = BriefParticipantCreate(
            user_id=uuid.uuid4(),
            participant_role="viewer",
        )
        assert data.can_edit is False
        assert data.can_approve is False
        assert data.can_request_revision is False


class TestRoleBlocking:
    def test_platform_admin_role_blocked_in_agency_invite(self) -> None:
        """AgencyInviteRequest rejects platform_admin as role."""
        from pydantic import ValidationError

        from app.schemas.invitation import AgencyInviteRequest

        with pytest.raises(ValidationError):
            AgencyInviteRequest(
                email="test@example.com",
                role="platform_admin",
            )

    def test_platform_admin_role_blocked_in_brand_invite(self) -> None:
        """BrandInviteRequest rejects platform_admin as role."""
        from pydantic import ValidationError

        from app.schemas.invitation import BrandInviteRequest

        with pytest.raises(ValidationError):
            BrandInviteRequest(
                email="test@example.com",
                role="platform_admin",
            )

    def test_agency_invite_valid_roles(self) -> None:
        """AgencyInviteRequest accepts valid AgencyMemberRole values."""
        from app.schemas.invitation import AgencyInviteRequest

        for role in AgencyMemberRole:
            req = AgencyInviteRequest(email="test@example.com", role=role.value)
            assert req.role == role.value

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.models.invitation import Invitation
from app.repositories.base import BaseRepository


class InvitationRepository(BaseRepository[Invitation]):
    model = Invitation

    async def get_by_token_hash(self, token_hash: str) -> Invitation | None:
        stmt = select(Invitation).where(
            Invitation.token_hash == token_hash,
            Invitation.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_for_email_and_agency(
        self,
        email: str,
        agency_id: UUID,
        invitation_type: str = "agency",
    ) -> Invitation | None:
        """Return the most recent pending invitation for email+agency."""
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        stmt = (
            select(Invitation)
            .where(
                Invitation.email == email.lower(),
                Invitation.agency_id == agency_id,
                Invitation.invitation_type == invitation_type,
                Invitation.accepted_at.is_(None),
                Invitation.revoked_at.is_(None),
                Invitation.deleted_at.is_(None),
                Invitation.expires_at > now,
            )
            .order_by(Invitation.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_agency(
        self, agency_id: UUID, *, include_expired: bool = False
    ) -> list[Invitation]:
        from datetime import UTC, datetime

        stmt = select(Invitation).where(
            Invitation.agency_id == agency_id,
            Invitation.deleted_at.is_(None),
        )
        if not include_expired:
            now = datetime.now(UTC)
            stmt = stmt.where(Invitation.expires_at > now)
        result = await self.session.execute(stmt.order_by(Invitation.created_at.desc()))
        return list(result.scalars().all())

    async def list_by_brand(
        self, brand_id: UUID, *, include_expired: bool = False
    ) -> list[Invitation]:
        from datetime import UTC, datetime

        stmt = select(Invitation).where(
            Invitation.brand_id == brand_id,
            Invitation.invitation_type == "brand",
            Invitation.deleted_at.is_(None),
        )
        if not include_expired:
            now = datetime.now(UTC)
            stmt = stmt.where(Invitation.expires_at > now)
        result = await self.session.execute(stmt.order_by(Invitation.created_at.desc()))
        return list(result.scalars().all())

    async def list_pending_for_email(self, email: str) -> list[Invitation]:
        """Return all pending invitations for a given email address (cross-agency)."""
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        stmt = (
            select(Invitation)
            .where(
                Invitation.email == email.lower(),
                Invitation.accepted_at.is_(None),
                Invitation.revoked_at.is_(None),
                Invitation.rejected_at.is_(None),
                Invitation.deleted_at.is_(None),
                Invitation.expires_at > now,
            )
            .order_by(Invitation.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

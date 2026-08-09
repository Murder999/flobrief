"""BrandApprovalDecisionService — single, concurrency-safe entry point for
brand-portal approve / request-revision / reject decisions.

Locks the Brief row (SELECT ... FOR UPDATE) before validating status, so two
simultaneous decisions on the same brief cannot both succeed: the second
request blocks until the first commits, then re-reads the already-updated
status and is rejected by the normal status-guard.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.brand_portal_auth import BrandPortalContext
from app.models.activity import ActivityLog
from app.models.approval import Approval, ApprovalEvent
from app.models.brief import Brief
from app.models.comment import Comment, CommentThread
from app.models.enums import ApprovalStatus, BriefStatus, NotificationEventType
from app.services.notification_dispatcher import NotificationDispatcher

Decision = Literal["approve", "revision_requested", "rejected"]

_DECIDABLE_STATUSES = (BriefStatus.IN_REVIEW.value, BriefStatus.READY_FOR_REVIEW.value)

_BRIEF_STATUS_FOR_DECISION: dict[Decision, str] = {
    "approve": BriefStatus.APPROVED.value,
    "revision_requested": BriefStatus.REVISION_REQUESTED.value,
    "rejected": BriefStatus.REJECTED.value,
}

_ACTIVITY_ACTION_FOR_DECISION: dict[Decision, str] = {
    "approve": "brief.approved_by_brand",
    "revision_requested": "brief.revision_requested_by_brand",
    "rejected": "brief.rejected_by_brand",
}

_NOTIFICATION_EVENT_FOR_DECISION: dict[Decision, str] = {
    "approve": NotificationEventType.BRIEF_APPROVED.value,
    "revision_requested": NotificationEventType.BRIEF_REVISION_REQUESTED.value,
    "rejected": NotificationEventType.BRIEF_REJECTED.value,
}

_COMMENT_AUTHOR_PREFIX: dict[Decision, str] = {
    "approve": "approval",
    "revision_requested": "revision",
    "rejected": "rejection",
}

_SUMMARY_FOR_DECISION: dict[Decision, str] = {
    "approve": "Brief onaylandı: {title}",
    "revision_requested": "Revizyon istendi: {title}",
    "rejected": "Brief reddedildi: {title}",
}


class BrandApprovalDecisionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def decide(
        self,
        brief_id: uuid.UUID,
        ctx: BrandPortalContext,
        decision: Decision,
        note_or_reason: str | None,
    ) -> Brief:
        brief = await self._lock_brief(brief_id, ctx.brand.id)
        if brief is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Brief bulunamadı")
        if brief.status not in _DECIDABLE_STATUSES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Brief karar için uygun durumda değil (mevcut durum: {brief.status})",
            )

        approval = await self._get_or_create_approval(brief, ctx)
        if approval.status != ApprovalStatus.PENDING.value:
            # Unreachable in practice given the row lock above; kept as defense in depth.
            raise HTTPException(status.HTTP_409_CONFLICT, "Bu onay zaten karara bağlanmış")

        now = datetime.now(UTC)
        approval.status = decision
        approval.decided_at = now
        approval.decided_by_user_id = ctx.user.id

        self.db.add(
            ApprovalEvent(
                id=uuid.uuid4(),
                approval_id=approval.id,
                event_type=decision,
                actor_type="brand_user",
                actor_user_id=ctx.user.id,
                actor_email=ctx.user.email,
                event_metadata={"note": note_or_reason} if note_or_reason else None,
            )
        )

        brief.status = _BRIEF_STATUS_FOR_DECISION[decision]
        brief.updated_at = now
        brief.updated_by_id = ctx.user.id

        if note_or_reason:
            await self._add_comment(brief, ctx, note_or_reason, decision)

        self.db.add(
            ActivityLog(
                id=uuid.uuid4(),
                agency_id=brief.agency_id,
                brand_id=ctx.brand.id,
                actor_user_id=ctx.user.id,
                action=_ACTIVITY_ACTION_FOR_DECISION[decision],
                entity_type="brief",
                entity_id=brief.id,
                meta={"brand_name": ctx.brand.name, "note": (note_or_reason or "")[:200]},
                created_at=now,
            )
        )

        await NotificationDispatcher(self.db).emit(
            _NOTIFICATION_EVENT_FOR_DECISION[decision],
            payload={
                "brief_id": str(brief.id),
                "brief_title": brief.title,
                "brand_name": ctx.brand.name,
                "reason": (note_or_reason or "")[:500],
                "summary": _SUMMARY_FOR_DECISION[decision].format(title=brief.title),
            },
            agency_id=brief.agency_id,
            brand_id=ctx.brand.id,
            actor_user_id=ctx.user.id,
        )

        await self.db.commit()
        await self.db.refresh(brief)
        return brief

    async def _lock_brief(self, brief_id: uuid.UUID, brand_id: uuid.UUID) -> Brief | None:
        result = await self.db.execute(
            select(Brief)
            .where(Brief.id == brief_id, Brief.brand_id == brand_id, Brief.deleted_at.is_(None))
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def _get_or_create_approval(self, brief: Brief, ctx: BrandPortalContext) -> Approval:
        result = await self.db.execute(
            select(Approval)
            .where(
                Approval.brief_id == brief.id,
                Approval.status == ApprovalStatus.PENDING.value,
            )
            .order_by(Approval.created_at.desc())
            .with_for_update()
        )
        approval = result.scalars().first()
        if approval is not None:
            return approval

        approval = Approval(
            id=uuid.uuid4(),
            brief_id=brief.id,
            version_id=None,
            status=ApprovalStatus.PENDING.value,
            channel="brand_portal",
            requested_by_id=ctx.user.id,
        )
        self.db.add(approval)
        await self.db.flush()
        return approval

    async def _add_comment(
        self, brief: Brief, ctx: BrandPortalContext, body: str, decision: Decision
    ) -> None:
        result = await self.db.execute(
            select(CommentThread).where(
                CommentThread.brief_id == brief.id,
                CommentThread.brand_id == ctx.brand.id,
                CommentThread.thread_type == "brief",
                CommentThread.deleted_at.is_(None),
            )
        )
        thread = result.scalar_one_or_none()
        if thread is None:
            thread = CommentThread(
                id=uuid.uuid4(),
                agency_id=brief.agency_id,
                brand_id=ctx.brand.id,
                brief_id=brief.id,
                thread_type="brief",
                status="open",
                created_by_id=ctx.user.id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self.db.add(thread)
            await self.db.flush()

        prefix = _COMMENT_AUTHOR_PREFIX[decision]
        self.db.add(
            Comment(
                id=uuid.uuid4(),
                thread_id=thread.id,
                author_user_id=ctx.user.id,
                author_name=ctx.user.full_name,
                author_email=f"{prefix}:{ctx.user.email}",
                body=body,
                visibility="client_visible",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

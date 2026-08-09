from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext
from app.models.asset import Asset, AssetLink
from app.models.brief import Brief
from app.models.comment import Comment, CommentThread
from app.models.enums import NotificationEventType
from app.repositories.comment import CommentRepository, CommentThreadRepository
from app.schemas.asset import AssetRead
from app.schemas.comment import (
    AddCommentRequest,
    CommentRead,
    ThreadCreate,
    ThreadRead,
    UpdateCommentRequest,
)
from app.services.mention_service import MentionService


class CommentService:
    def __init__(self, db: AsyncSession, workspace: WorkspaceContext) -> None:
        self.db = db
        self.workspace = workspace
        self.thread_repo = CommentThreadRepository(db)
        self.comment_repo = CommentRepository(db)
        self.mention_service = MentionService(db)

    async def _require_brief(self, brief_id: uuid.UUID) -> Brief:
        result = await self.db.execute(
            select(Brief).where(
                Brief.id == brief_id,
                Brief.agency_id == self.workspace.agency.id,
                Brief.deleted_at.is_(None),
            )
        )
        brief = result.scalar_one_or_none()
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")
        return brief

    async def _require_thread(self, thread_id: uuid.UUID) -> CommentThread:
        thread = await self.thread_repo.get_by_id(thread_id)
        if not thread or thread.agency_id != self.workspace.agency.id:
            raise HTTPException(status_code=404, detail="Thread not found")
        return thread

    async def _load_comment_attachments(self, comment_id: uuid.UUID) -> list[AssetRead]:
        rows = await self.db.execute(
            select(Asset)
            .join(AssetLink, AssetLink.asset_id == Asset.id)
            .where(
                AssetLink.comment_id == comment_id,
                Asset.deleted_at.is_(None),
            )
            .order_by(Asset.created_at.asc())
        )
        return [AssetRead.model_validate(a) for a in rows.scalars().all()]

    async def _build_comment_read(self, comment: Comment) -> CommentRead:
        attachments = await self._load_comment_attachments(comment.id)
        mentions = await self.mention_service.get_inline_mentions(
            source_type="comment", source_id=comment.id
        )
        data = CommentRead.model_validate(comment)
        return data.model_copy(update={"attachments": attachments, "mentions": mentions})

    async def _link_attachments(
        self, comment_id: uuid.UUID, brief_id: uuid.UUID | None, attachment_ids: list[uuid.UUID]
    ) -> None:
        for asset_id in attachment_ids:
            asset = await self.db.scalar(
                select(Asset).where(
                    Asset.id == asset_id,
                    Asset.agency_id == self.workspace.agency.id,
                    Asset.deleted_at.is_(None),
                )
            )
            if asset:
                self.db.add(
                    AssetLink(
                        asset_id=asset_id,
                        brief_id=brief_id,
                        comment_id=comment_id,
                    )
                )

    async def _build_thread_read(self, thread: CommentThread) -> ThreadRead:
        comments = await self.comment_repo.list_for_thread(thread.id)
        comment_reads = [await self._build_comment_read(c) for c in comments]
        data = ThreadRead.model_validate(thread)
        return data.model_copy(update={"comments": comment_reads})

    async def _dispatch_mentions(
        self,
        *,
        comment_id: uuid.UUID,
        brief_id: uuid.UUID,
        brand_id: uuid.UUID | None,
        body: str,
        brief_title: str,
        actor_name: str,
        mentioned_user_ids: list[uuid.UUID],
    ) -> None:
        """Durable @mention pipeline (see MentionService) — replaces the old
        regex-over-body approach. Notifies only newly-added mentions."""
        if not mentioned_user_ids:
            return
        excerpt = body[:120] + ("…" if len(body) > 120 else "")
        await self.mention_service.sync_mentions_for_source(
            agency_id=self.workspace.agency.id,
            brand_id=brand_id,
            brief_id=brief_id,
            deliverable_id=None,
            source_type="comment",
            source_id=comment_id,
            actor_user_id=self.workspace.user.id,
            actor_name=actor_name,
            body_text=body,
            mentioned_user_ids=mentioned_user_ids,
            portal="agency",
            notification_event_type=NotificationEventType.MENTIONED_IN_COMMENT.value,
            notification_payload_extra={
                "brief_id": str(brief_id),
                "brief_title": brief_title,
                "comment_id": str(comment_id),
                "comment_preview": excerpt,
                "summary": f'{actor_name} sizi bir yorumda etiketledi: "{excerpt}"',
            },
        )

    async def create_thread(self, brief_id: uuid.UUID, payload: ThreadCreate) -> ThreadRead:
        brief = await self._require_brief(brief_id)

        thread = await self.thread_repo.create(
            {
                "agency_id": self.workspace.agency.id,
                "brief_id": brief_id,
                "brand_id": payload.brand_id,
                "field_key": payload.field_key,
                "approval_id": payload.approval_id,
                "asset_id": payload.asset_id,
                "thread_type": payload.thread_type,
                "status": "open",
                "created_by_id": self.workspace.user.id,
            }
        )

        initial = await self.comment_repo.create(
            {
                "thread_id": thread.id,
                "author_user_id": self.workspace.user.id,
                "author_name": self.workspace.user.full_name,
                "author_job_title": getattr(self.workspace.user, "job_title", None),
                "body": payload.initial_comment,
                "visibility": payload.visibility,
            }
        )

        if payload.attachment_ids:
            await self._link_attachments(initial.id, brief_id, payload.attachment_ids)

        await self._dispatch_mentions(
            comment_id=initial.id,
            brief_id=brief_id,
            brand_id=payload.brand_id,
            body=payload.initial_comment,
            brief_title=brief.title,
            actor_name=self.workspace.user.full_name,
            mentioned_user_ids=payload.mentioned_user_ids,
        )

        await self.db.commit()
        await self.db.refresh(thread)
        return await self._build_thread_read(thread)

    async def list_threads(self, brief_id: uuid.UUID) -> list[ThreadRead]:
        await self._require_brief(brief_id)
        threads = await self.thread_repo.list_for_brief(brief_id, self.workspace.agency.id)
        result = []
        for t in threads:
            result.append(await self._build_thread_read(t))
        return result

    async def add_comment(self, thread_id: uuid.UUID, payload: AddCommentRequest) -> CommentRead:
        thread = await self._require_thread(thread_id)

        comment = await self.comment_repo.create(
            {
                "thread_id": thread_id,
                "author_user_id": self.workspace.user.id,
                "author_name": self.workspace.user.full_name,
                "author_job_title": getattr(self.workspace.user, "job_title", None),
                "body": payload.body,
                "visibility": payload.visibility,
            }
        )

        if payload.attachment_ids:
            await self._link_attachments(comment.id, thread.brief_id, payload.attachment_ids)

        if thread.brief_id:
            brief_res = await self.db.execute(select(Brief).where(Brief.id == thread.brief_id))
            brief = brief_res.scalar_one_or_none()
            if brief:
                await self._dispatch_mentions(
                    comment_id=comment.id,
                    brief_id=thread.brief_id,
                    brand_id=thread.brand_id,
                    body=payload.body,
                    brief_title=brief.title,
                    actor_name=self.workspace.user.full_name,
                    mentioned_user_ids=payload.mentioned_user_ids,
                )
                from app.services.notification_dispatcher import NotificationDispatcher

                dispatcher = NotificationDispatcher(self.db)
                recipient_ids = [
                    u.id for u in await dispatcher.get_agency_members(self.workspace.agency.id)
                ]
                # A client_visible reply is one the brand can actually see —
                # notify their portal users too, not just the agency team.
                # Internal-only replies keep the prior agency-only behavior.
                if payload.visibility == "client_visible" and thread.brand_id is not None:
                    recipient_ids += [
                        u.id for u in await dispatcher.get_brand_members(thread.brand_id)
                    ]
                await dispatcher.emit(
                    NotificationEventType.COMMENT_ADDED.value,
                    payload={
                        "brief_id": str(thread.brief_id),
                        "brief_title": brief.title,
                        "comment_id": str(comment.id),
                        "comment_preview": payload.body[:200],
                        "actor_name": self.workspace.user.full_name,
                        "summary": f"{self.workspace.user.full_name}: {payload.body[:100]}",
                    },
                    agency_id=self.workspace.agency.id,
                    brand_id=thread.brand_id,
                    actor_user_id=self.workspace.user.id,
                    recipient_ids=recipient_ids,
                )

        await self.db.commit()
        await self.db.refresh(comment)
        return await self._build_comment_read(comment)

    async def update_comment(
        self,
        thread_id: uuid.UUID,
        comment_id: uuid.UUID,
        payload: UpdateCommentRequest,
    ) -> CommentRead:
        await self._require_thread(thread_id)

        comment = await self.comment_repo.get_by_id(comment_id)
        if not comment or comment.thread_id != thread_id:
            raise HTTPException(status_code=404, detail="Comment not found")
        if comment.author_user_id != self.workspace.user.id:
            raise HTTPException(status_code=403, detail="Can only edit your own comments")

        updated = await self.comment_repo.update(comment, {"body": payload.body})

        thread = await self._require_thread(thread_id)
        if thread.brief_id:
            brief_res = await self.db.execute(select(Brief).where(Brief.id == thread.brief_id))
            brief = brief_res.scalar_one_or_none()
            if brief:
                await self._dispatch_mentions(
                    comment_id=updated.id,
                    brief_id=thread.brief_id,
                    brand_id=thread.brand_id,
                    body=payload.body,
                    brief_title=brief.title,
                    actor_name=self.workspace.user.full_name,
                    mentioned_user_ids=payload.mentioned_user_ids,
                )

        await self.db.commit()
        await self.db.refresh(updated)
        return await self._build_comment_read(updated)

    async def delete_comment(self, thread_id: uuid.UUID, comment_id: uuid.UUID) -> None:
        await self._require_thread(thread_id)

        comment = await self.comment_repo.get_by_id(comment_id)
        if not comment or comment.thread_id != thread_id:
            raise HTTPException(status_code=404, detail="Comment not found")
        if comment.author_user_id != self.workspace.user.id:
            raise HTTPException(status_code=403, detail="Can only delete your own comments")

        comment.soft_delete()
        await self.db.commit()

    async def resolve_thread(self, thread_id: uuid.UUID) -> ThreadRead:
        thread = await self._require_thread(thread_id)
        now = datetime.now(UTC)
        await self.thread_repo.update(thread, {"status": "resolved", "resolved_at": now})
        await self.db.commit()
        await self.db.refresh(thread)
        return await self._build_thread_read(thread)

    async def reopen_thread(self, thread_id: uuid.UUID) -> ThreadRead:
        thread = await self._require_thread(thread_id)
        await self.thread_repo.update(thread, {"status": "open", "resolved_at": None})
        await self.db.commit()
        await self.db.refresh(thread)
        return await self._build_thread_read(thread)

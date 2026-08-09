from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.notification_dispatcher import NotificationDispatcher

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext
from app.core.rbac import Permission
from app.models.enums import BriefStatus, NotificationEventType
from app.repositories.activity import ActivityLogRepository
from app.repositories.brand import BrandRepository
from app.repositories.brief import (
    BriefAssigneeRepository,
    BriefFieldValueRepository,
    BriefRepository,
)
from app.repositories.calendar import CalendarItemRepository
from app.schemas.brief import (
    AssigneeAdd,
    AssigneeRead,
    BriefCreate,
    BriefDetail,
    BriefFieldValuesUpdate,
    BriefListResponse,
    BriefRead,
    BriefStatusUpdate,
    BriefUpdate,
    FieldValueRead,
)

_STATUS_TRANSITIONS: dict[str, list[str]] = {
    # Agency-created brief (source="agency"): direct in_review → brand approval
    BriefStatus.DRAFT: [BriefStatus.IN_REVIEW, BriefStatus.SUBMITTED, BriefStatus.ARCHIVED],
    BriefStatus.IN_REVIEW: [
        BriefStatus.ACCEPTED,
        BriefStatus.REVISION_REQUESTED,
        BriefStatus.APPROVED,
        BriefStatus.ARCHIVED,
    ],
    # Brand-portal brief full workflow
    BriefStatus.SUBMITTED: [BriefStatus.ACCEPTED, BriefStatus.ARCHIVED],
    BriefStatus.ACCEPTED: [BriefStatus.IN_PRODUCTION, BriefStatus.ARCHIVED],
    BriefStatus.IN_PRODUCTION: [BriefStatus.READY_FOR_REVIEW, BriefStatus.ARCHIVED],
    BriefStatus.READY_FOR_REVIEW: [
        BriefStatus.REVISION_REQUESTED,
        BriefStatus.APPROVED,
        BriefStatus.ARCHIVED,
    ],
    BriefStatus.REVISION_REQUESTED: [
        BriefStatus.IN_PRODUCTION,
        BriefStatus.READY_FOR_REVIEW,
        BriefStatus.ARCHIVED,
    ],
    BriefStatus.APPROVED: [BriefStatus.COMPLETED, BriefStatus.SCHEDULED, BriefStatus.ARCHIVED],
    BriefStatus.COMPLETED: [BriefStatus.ARCHIVED],
    BriefStatus.SCHEDULED: [BriefStatus.ARCHIVED],
    BriefStatus.ARCHIVED: [],
}


class BriefService:
    def __init__(self, db: AsyncSession, workspace: WorkspaceContext) -> None:
        self.db = db
        self.workspace = workspace
        self.repo = BriefRepository(db)
        self.fv_repo = BriefFieldValueRepository(db)
        self.assignee_repo = BriefAssigneeRepository(db)
        self._activity = ActivityLogRepository(db)
        self._cal = CalendarItemRepository(db)

    def _dispatcher(self) -> NotificationDispatcher:
        from app.services.notification_dispatcher import NotificationDispatcher

        return NotificationDispatcher(self.db)

    # ------------------------------------------------------------------
    # Permission helpers
    # ------------------------------------------------------------------

    def _require(self, permission: Permission) -> None:
        if not self.workspace.has_permission(permission):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def list_briefs(
        self,
        *,
        brand_id: uuid.UUID | None = None,
        status: str | None = None,
        priority: str | None = None,
        assignee_id: uuid.UUID | None = None,
        deadline_before: str | None = None,
        search: str | None = None,
        source: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> BriefListResponse:
        self._require(Permission.BRIEF_VIEW)
        items, total = await self.repo.list(
            self.workspace.agency.id,
            brand_id=brand_id,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
            deadline_before=deadline_before,
            search=search,
            source=source,
            offset=offset,
            limit=limit,
        )
        return BriefListResponse(
            items=[BriefRead.model_validate(b) for b in items],
            total=total,
            offset=offset,
            limit=limit,
        )

    async def get_detail(self, brief_id: uuid.UUID) -> BriefDetail:
        self._require(Permission.BRIEF_VIEW)
        brief = await self.repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")

        field_values = await self.fv_repo.get_for_brief(brief_id)
        assignees = await self.assignee_repo.get_for_brief(brief_id)
        cal_item = await self._cal.get_by_brief_id(brief_id)

        detail = BriefDetail.model_validate(brief)
        detail.field_values = [FieldValueRead.model_validate(fv) for fv in field_values]
        detail.assignees = [AssigneeRead.model_validate(a) for a in assignees]
        detail.linked_calendar_item_id = cal_item.id if cal_item else None
        return detail

    async def create(self, payload: BriefCreate) -> BriefDetail:
        self._require(Permission.BRIEF_CREATE)

        if payload.brand_id:
            brand_repo = BrandRepository(self.db)
            brand = await brand_repo.get_by_id_and_agency(
                payload.brand_id, self.workspace.agency.id
            )
            if not brand:
                raise HTTPException(status_code=404, detail="Brand not found")

        meta: dict[str, Any] = {}
        if payload.platforms:
            meta["platforms"] = payload.platforms
        if payload.content_types:
            meta["content_types"] = payload.content_types
        if payload.reference_links:
            meta["reference_links"] = payload.reference_links

        from app.core.html_sanitizer import sanitize_html

        data: dict[str, Any] = {
            "agency_id": self.workspace.agency.id,
            "brand_id": payload.brand_id,
            "template_id": payload.template_id,
            "title": payload.title,
            "description": payload.description,
            "description_html": sanitize_html(payload.description_html),
            "status": BriefStatus.DRAFT,
            "priority": payload.priority.value,
            "start_date": payload.start_date,
            "draft_date": payload.draft_date,
            "feedback_date": payload.feedback_date,
            "deadline": payload.deadline,
            "publish_date": payload.publish_date,
            "platforms": payload.platforms or None,
            "content_types": payload.content_types or None,
            "created_by_id": self.workspace.user.id,
            "updated_by_id": None,
            "source": "agency",
            "meta": meta or None,
            "estimated_hours": payload.estimated_hours,
            "estimated_hours_by_category": payload.estimated_hours_by_category,
        }
        brief = await self.repo.create(data)

        for uid in payload.assignee_ids:
            await self.assignee_repo.add(brief.id, uid, None)

        if payload.deadline and payload.add_to_calendar:
            due_dt = datetime.fromisoformat(f"{payload.deadline}T12:00:00").replace(tzinfo=UTC)
            await self._cal.create(
                {
                    "agency_id": self.workspace.agency.id,
                    "brand_id": payload.brand_id,
                    "brief_id": brief.id,
                    "title": payload.title,
                    "item_type": "campaign",
                    "platform": "other",
                    "status": "planned",
                    "due_at": due_dt,
                    "created_by_id": self.workspace.user.id,
                }
            )
            await self._activity.create(
                action="brief.calendar_synced",
                entity_type="brief",
                entity_id=brief.id,
                agency_id=self.workspace.agency.id,
                brand_id=payload.brand_id,
                actor_user_id=self.workspace.user.id,
                meta={"deadline": payload.deadline},
            )

        await self._activity.create(
            action="brief.created",
            entity_type="brief",
            entity_id=brief.id,
            agency_id=self.workspace.agency.id,
            brand_id=payload.brand_id,
            actor_user_id=self.workspace.user.id,
            meta={"title": payload.title},
        )
        await self._dispatcher().emit(
            NotificationEventType.BRIEF_CREATED.value,
            payload={
                "brief_id": str(brief.id),
                "brief_title": payload.title,
                "summary": f"Yeni brief: {payload.title}",
            },
            agency_id=self.workspace.agency.id,
            brand_id=payload.brand_id,
            actor_user_id=self.workspace.user.id,
        )
        await self.db.commit()
        return await self.get_detail(brief.id)

    async def update(self, brief_id: uuid.UUID, payload: BriefUpdate) -> BriefDetail:
        self._require(Permission.BRIEF_UPDATE)
        brief = await self.repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")

        if payload.brand_id is not None:
            brand_repo = BrandRepository(self.db)
            brand = await brand_repo.get_by_id_and_agency(
                payload.brand_id, self.workspace.agency.id
            )
            if not brand:
                raise HTTPException(status_code=404, detail="Brand not found")

        from app.core.html_sanitizer import sanitize_html

        patch = payload.model_dump(exclude_unset=True)
        if "priority" in patch and hasattr(patch["priority"], "value"):
            patch["priority"] = patch["priority"].value
        if "description_html" in patch:
            patch["description_html"] = sanitize_html(patch["description_html"])
        patch["updated_by_id"] = self.workspace.user.id
        await self.repo.update(brief, patch)

        if "deadline" in patch and patch["deadline"]:
            cal_item = await self._cal.get_by_brief_id(brief_id)
            if cal_item:
                new_due = datetime.fromisoformat(f"{patch['deadline']}T12:00:00").replace(
                    tzinfo=UTC
                )
                await self._cal.update(cal_item, {"due_at": new_due})
                await self._activity.create(
                    action="brief.deadline_changed",
                    entity_type="brief",
                    entity_id=brief_id,
                    agency_id=self.workspace.agency.id,
                    actor_user_id=self.workspace.user.id,
                    meta={"deadline": patch["deadline"]},
                )

        await self.db.commit()
        return await self.get_detail(brief_id)

    async def change_status(self, brief_id: uuid.UUID, payload: BriefStatusUpdate) -> BriefDetail:
        self._require(Permission.BRIEF_SUBMIT_APPROVAL)
        brief = await self.repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")

        allowed = _STATUS_TRANSITIONS.get(brief.status, [])
        if payload.status.value not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot transition from '{brief.status}' to '{payload.status.value}'",
            )
        await self.repo.update(
            brief,
            {"status": payload.status.value, "updated_by_id": self.workspace.user.id},
        )
        await self._activity.create(
            action=f"brief.status_changed.{payload.status.value}",
            entity_type="brief",
            entity_id=brief_id,
            agency_id=self.workspace.agency.id,
            actor_user_id=self.workspace.user.id,
            meta={"status": payload.status.value},
        )
        await self._emit_status_notification(brief_id, brief, payload.status.value)
        await self.db.commit()
        return await self.get_detail(brief_id)

    async def _emit_status_notification(
        self, brief_id: uuid.UUID, brief: Any, new_status: str
    ) -> None:
        d = self._dispatcher()
        agency_id = self.workspace.agency.id
        actor_id = self.workspace.user.id

        if new_status == BriefStatus.IN_REVIEW.value:
            if brief.brand_id:
                brand_recipients = await d.get_brand_members(brief.brand_id)
                recipient_ids = [u.id for u in brand_recipients]
            else:
                recipient_ids = None
            await d.emit(
                NotificationEventType.BRIEF_SUBMITTED.value,
                payload={
                    "brief_id": str(brief_id),
                    "brief_title": brief.title,
                    "agency_name": self.workspace.agency.name,
                    "status_version": brief.updated_at.isoformat(),
                    "summary": f"Brief onayınızı bekliyor: {brief.title}",
                },
                agency_id=agency_id,
                brand_id=brief.brand_id,
                actor_user_id=actor_id,
                recipient_ids=recipient_ids if brief.brand_id else None,
            )

        elif new_status == BriefStatus.ACCEPTED.value:
            await d.emit(
                NotificationEventType.BRIEF_ACCEPTED.value,
                payload={
                    "brief_id": str(brief_id),
                    "brief_title": brief.title,
                    "status_version": brief.updated_at.isoformat(),
                    "summary": f"Brief kabul edildi: {brief.title}",
                },
                agency_id=agency_id,
                brand_id=brief.brand_id,
                actor_user_id=actor_id,
            )

        elif new_status == BriefStatus.IN_PRODUCTION.value:
            await d.emit(
                NotificationEventType.BRIEF_PRODUCTION_STARTED.value,
                payload={
                    "brief_id": str(brief_id),
                    "brief_title": brief.title,
                    "status_version": brief.updated_at.isoformat(),
                    "summary": f"Brief üretimde: {brief.title}",
                },
                agency_id=agency_id,
                brand_id=brief.brand_id,
                actor_user_id=actor_id,
            )

        elif new_status == BriefStatus.READY_FOR_REVIEW.value:
            if brief.brand_id:
                brand_recipients = await d.get_brand_members(brief.brand_id)
                recipient_ids = [u.id for u in brand_recipients]
            else:
                recipient_ids = None
            await d.emit(
                NotificationEventType.BRIEF_READY_FOR_REVIEW.value,
                payload={
                    "brief_id": str(brief_id),
                    "brief_title": brief.title,
                    "agency_name": self.workspace.agency.name,
                    "status_version": brief.updated_at.isoformat(),
                    "summary": f"Brief incelemenizi bekliyor: {brief.title}",
                },
                agency_id=agency_id,
                brand_id=brief.brand_id,
                actor_user_id=actor_id,
                recipient_ids=recipient_ids if brief.brand_id else None,
            )

        elif new_status == BriefStatus.APPROVED.value:
            await d.emit(
                NotificationEventType.BRIEF_APPROVED.value,
                payload={
                    "brief_id": str(brief_id),
                    "brief_title": brief.title,
                    "status_version": brief.updated_at.isoformat(),
                    "summary": f"Brief onaylandı: {brief.title}",
                },
                agency_id=agency_id,
                brand_id=brief.brand_id,
                actor_user_id=actor_id,
            )

        elif new_status == BriefStatus.REVISION_REQUESTED.value:
            await d.emit(
                NotificationEventType.BRIEF_REVISION_REQUESTED.value,
                payload={
                    "brief_id": str(brief_id),
                    "brief_title": brief.title,
                    "reason": "Revizyon talep edildi.",
                    "status_version": brief.updated_at.isoformat(),
                    "summary": f"Revizyon istendi: {brief.title}",
                },
                agency_id=agency_id,
                brand_id=brief.brand_id,
                actor_user_id=actor_id,
            )

        elif new_status == BriefStatus.COMPLETED.value:
            await d.emit(
                NotificationEventType.BRIEF_COMPLETED.value,
                payload={
                    "brief_id": str(brief_id),
                    "brief_title": brief.title,
                    "status_version": brief.updated_at.isoformat(),
                    "summary": f"Brief tamamlandı: {brief.title}",
                },
                agency_id=agency_id,
                brand_id=brief.brand_id,
                actor_user_id=actor_id,
            )

    async def archive(self, brief_id: uuid.UUID) -> None:
        self._require(Permission.BRIEF_UPDATE)
        brief = await self.repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")
        cal_item = await self._cal.get_by_brief_id(brief_id)
        if cal_item:
            await self._cal.update(cal_item, {"status": "cancelled"})

        await self.repo.soft_delete(brief)
        await self._activity.create(
            action="brief.archived",
            entity_type="brief",
            entity_id=brief_id,
            agency_id=self.workspace.agency.id,
            actor_user_id=self.workspace.user.id,
            meta={"title": brief.title},
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Field values
    # ------------------------------------------------------------------

    async def update_field_values(
        self, brief_id: uuid.UUID, payload: BriefFieldValuesUpdate
    ) -> BriefDetail:
        self._require(Permission.BRIEF_UPDATE)
        brief = await self.repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")

        await self.fv_repo.upsert_many(
            brief_id,
            [{"template_field_id": v.template_field_id, "value": v.value} for v in payload.values],
        )
        await self.repo.update(brief, {"updated_by_id": self.workspace.user.id})
        await self.db.commit()
        return await self.get_detail(brief_id)

    # ------------------------------------------------------------------
    # Assignees
    # ------------------------------------------------------------------

    async def assign_user(self, brief_id: uuid.UUID, payload: AssigneeAdd) -> AssigneeRead:
        self._require(Permission.BRIEF_UPDATE)
        brief = await self.repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")

        if await self.assignee_repo.exists(brief_id, payload.user_id):
            raise HTTPException(status_code=409, detail="User already assigned")

        assignee = await self.assignee_repo.add(brief_id, payload.user_id, payload.role_label)
        await self.db.commit()
        return AssigneeRead.model_validate(assignee)

    async def unassign_user(self, brief_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self._require(Permission.BRIEF_UPDATE)
        brief = await self.repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")

        removed = await self.assignee_repo.remove(brief_id, user_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Assignee not found")
        await self.db.commit()

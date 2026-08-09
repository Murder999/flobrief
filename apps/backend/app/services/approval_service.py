from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext
from app.core.config import settings
from app.core.rbac import Permission
from app.models.approval import Approval, ApprovalToken, BriefVersion
from app.models.brief import Brief, BriefFieldValue
from app.models.brief_template import BriefTemplate, BriefTemplateField, BriefTemplateSection
from app.models.enums import ApprovalStatus, BriefStatus
from app.repositories.approval import (
    ApprovalCommentRepository,
    ApprovalEventRepository,
    ApprovalRepository,
    ApprovalTokenRepository,
    BriefChangeLogRepository,
    BriefVersionRepository,
)
from app.repositories.brief import BriefRepository
from app.schemas.approval import (
    AddPublicCommentRequest,
    ApprovalCommentRead,
    ApprovalRead,
    BriefVersionRead,
    BriefVersionSummary,
    PublicApprovalView,
    PublicApproveRequest,
    PublicFieldValue,
    PublicRevisionRequest,
    PublicSection,
    SendToApprovalResponse,
)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class ApprovalService:
    def __init__(self, db: AsyncSession, workspace: WorkspaceContext) -> None:
        self.db = db
        self.workspace = workspace
        self.version_repo = BriefVersionRepository(db)
        self.changelog_repo = BriefChangeLogRepository(db)
        self.approval_repo = ApprovalRepository(db)
        self.token_repo = ApprovalTokenRepository(db)
        self.event_repo = ApprovalEventRepository(db)
        self.comment_repo = ApprovalCommentRepository(db)
        self.brief_repo = BriefRepository(db)

    def _require(self, perm: Permission) -> None:
        if not self.workspace.has_permission(perm):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    # ------------------------------------------------------------------
    # Snapshot building
    # ------------------------------------------------------------------

    async def _build_snapshot(self, brief: Brief) -> dict[str, Any]:
        fv_result = await self.db.execute(
            select(BriefFieldValue).where(BriefFieldValue.brief_id == brief.id)
        )
        field_values = {str(fv.template_field_id): fv.value for fv in fv_result.scalars().all()}

        brand_name: str | None = None
        if brief.brand_id:
            from app.models.brand import Brand

            brand_result = await self.db.execute(
                select(Brand).where(Brand.id == brief.brand_id, Brand.deleted_at.is_(None))
            )
            brand = brand_result.scalar_one_or_none()
            brand_name = brand.name if brand else None

        sections: list[dict[str, Any]] = []
        template_name: str | None = None
        template_industry: str | None = None

        if brief.template_id:
            tmpl_result = await self.db.execute(
                select(BriefTemplate).where(BriefTemplate.id == brief.template_id)
            )
            tmpl = tmpl_result.scalar_one_or_none()
            if tmpl:
                template_name = tmpl.name
                template_industry = tmpl.industry

                secs_result = await self.db.execute(
                    select(BriefTemplateSection)
                    .where(BriefTemplateSection.template_id == tmpl.id)
                    .order_by(BriefTemplateSection.sort_order.asc())
                )
                for sec in secs_result.scalars().all():
                    fields_result = await self.db.execute(
                        select(BriefTemplateField)
                        .where(BriefTemplateField.section_id == sec.id)
                        .order_by(BriefTemplateField.sort_order.asc())
                    )
                    field_list = []
                    for f in fields_result.scalars().all():
                        field_list.append(
                            {
                                "field_id": str(f.id),
                                "field_key": f.field_key,
                                "label": f.label,
                                "field_type": f.field_type,
                                "is_required": f.is_required,
                                "options": f.options,
                                "placeholder": f.placeholder,
                                "value": field_values.get(str(f.id)),
                            }
                        )
                    sections.append(
                        {
                            "title": sec.title,
                            "description": sec.description,
                            "fields": field_list,
                        }
                    )

        return {
            "brief": {
                "title": brief.title,
                "description": brief.description,
                "priority": brief.priority,
                "deadline": brief.deadline,
            },
            "template": {
                "name": template_name,
                "industry": template_industry,
            }
            if template_name
            else None,
            "brand_name": brand_name,
            "sections": sections,
        }

    # ------------------------------------------------------------------
    # Private: send to approval
    # ------------------------------------------------------------------

    async def send_to_approval(self, brief_id: uuid.UUID) -> SendToApprovalResponse:
        self._require(Permission.BRIEF_SUBMIT_APPROVAL)
        brief = await self.brief_repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")

        if brief.status not in (BriefStatus.DRAFT, BriefStatus.REVISION_REQUESTED):
            raise HTTPException(
                status_code=422,
                detail=f"Cannot send brief in status '{brief.status}' for approval",
            )

        snapshot = await self._build_snapshot(brief)

        version_number = await self.version_repo.next_version_number(brief_id)
        version = await self.version_repo.create(
            {
                "brief_id": brief_id,
                "version_number": version_number,
                "snapshot": snapshot,
                "created_by_id": self.workspace.user.id,
            }
        )

        approval = await self.approval_repo.create(
            {
                "brief_id": brief_id,
                "version_id": version.id,
                "status": ApprovalStatus.PENDING,
                "requested_by_id": self.workspace.user.id,
            }
        )

        raw_token = secrets.token_urlsafe(48)
        token_hash = _hash_token(raw_token)
        expires_at = datetime.now(UTC).replace(microsecond=0)
        from datetime import timedelta

        expires_at = expires_at + timedelta(hours=settings.APPROVAL_TOKEN_EXPIRE_HOURS)

        await self.token_repo.create(
            {
                "approval_id": approval.id,
                "token_hash": token_hash,
                "expires_at": expires_at,
            }
        )

        await self.event_repo.create(
            {
                "approval_id": approval.id,
                "event_type": "sent",
                "actor_type": "agency_user",
                "actor_user_id": self.workspace.user.id,
            }
        )

        brief.status = BriefStatus.IN_REVIEW
        brief.updated_by_id = self.workspace.user.id
        await self.db.flush()

        await self.db.commit()

        approval_url = f"{settings.FRONTEND_URL}/approve/{raw_token}"
        return SendToApprovalResponse(
            approval=ApprovalRead.model_validate(approval),
            approval_token=raw_token,
            approval_url=approval_url,
        )

    # ------------------------------------------------------------------
    # Private: list approvals + revoke
    # ------------------------------------------------------------------

    async def list_approvals(self, brief_id: uuid.UUID) -> list[ApprovalRead]:
        self._require(Permission.BRIEF_VIEW)
        brief = await self.brief_repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")
        approvals = await self.approval_repo.list_for_brief(brief_id)
        return [ApprovalRead.model_validate(a) for a in approvals]

    async def revoke_approval(self, brief_id: uuid.UUID, approval_id: uuid.UUID) -> ApprovalRead:
        self._require(Permission.BRIEF_SUBMIT_APPROVAL)
        brief = await self.brief_repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")

        approval = await self.approval_repo.get_by_id(approval_id, brief_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        if approval.status != ApprovalStatus.PENDING:
            raise HTTPException(status_code=422, detail="Only pending approvals can be revoked")

        now = datetime.now(UTC)
        token_result = await self.db.execute(
            select(ApprovalToken).where(
                ApprovalToken.approval_id == approval.id,
                ApprovalToken.revoked_at.is_(None),
            )
        )
        for tok in token_result.scalars().all():
            tok.revoked_at = now

        await self.approval_repo.update(approval, {"status": ApprovalStatus.CANCELLED})
        await self.event_repo.create(
            {
                "approval_id": approval.id,
                "event_type": "cancelled",
                "actor_type": "agency_user",
                "actor_user_id": self.workspace.user.id,
            }
        )

        if brief.status == BriefStatus.IN_REVIEW:
            brief.status = BriefStatus.DRAFT
            brief.updated_by_id = self.workspace.user.id
            await self.db.flush()

        await self.db.commit()
        return ApprovalRead.model_validate(approval)

    # ------------------------------------------------------------------
    # Private: versions
    # ------------------------------------------------------------------

    async def list_versions(self, brief_id: uuid.UUID) -> list[BriefVersionSummary]:
        self._require(Permission.BRIEF_VIEW)
        brief = await self.brief_repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")
        versions = await self.version_repo.list_for_brief(brief_id)
        return [BriefVersionSummary.model_validate(v) for v in versions]

    async def get_version(self, brief_id: uuid.UUID, version_id: uuid.UUID) -> BriefVersionRead:
        self._require(Permission.BRIEF_VIEW)
        brief = await self.brief_repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")
        version = await self.version_repo.get_by_id(version_id, brief_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        return BriefVersionRead.model_validate(version)

    # ------------------------------------------------------------------
    # Private: comments list (internal view)
    # ------------------------------------------------------------------

    async def list_comments(
        self, brief_id: uuid.UUID, approval_id: uuid.UUID
    ) -> list[ApprovalCommentRead]:
        self._require(Permission.BRIEF_VIEW)
        brief = await self.brief_repo.get_by_id(brief_id, self.workspace.agency.id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")
        approval = await self.approval_repo.get_by_id(approval_id, brief_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        comments = await self.comment_repo.list_for_approval(approval_id, include_internal=True)
        return [ApprovalCommentRead.model_validate(c) for c in comments]


class PublicApprovalService:
    """No auth required — only token-gated access to approval data."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.token_repo = ApprovalTokenRepository(db)
        self.approval_repo = ApprovalRepository(db)
        self.event_repo = ApprovalEventRepository(db)
        self.comment_repo = ApprovalCommentRepository(db)

    async def _resolve_token(self, raw_token: str) -> tuple[ApprovalToken, Approval]:
        token_hash = _hash_token(raw_token)
        token = await self.token_repo.get_by_hash(token_hash)
        if not token:
            raise HTTPException(status_code=404, detail="Approval link not found")
        if token.revoked_at is not None:
            raise HTTPException(status_code=410, detail="This approval link has been revoked")
        if datetime.now(UTC) > token.expires_at.replace(tzinfo=UTC):
            raise HTTPException(status_code=410, detail="This approval link has expired")
        if token.used_at is not None:
            raise HTTPException(status_code=409, detail="This approval has already been decided")

        approval_lookup = await self.token_repo.get_approval(token)
        if not approval_lookup:
            raise HTTPException(status_code=409, detail="This approval has already been decided")

        # Lock the Approval row so a concurrent decision (public-token or
        # brand-portal in-app, both of which lock this same row) cannot race.
        locked = await self.db.execute(
            select(Approval).where(Approval.id == approval_lookup.id).with_for_update()
        )
        approval = locked.scalar_one()
        if approval.status not in (ApprovalStatus.PENDING,):
            raise HTTPException(status_code=409, detail="This approval has already been decided")

        return token, approval

    async def get_by_token(self, raw_token: str) -> PublicApprovalView:
        token_hash = _hash_token(raw_token)
        token = await self.token_repo.get_by_hash(token_hash)
        if not token:
            raise HTTPException(status_code=404, detail="Approval link not found")

        if token.revoked_at is not None:
            raise HTTPException(status_code=410, detail="Bu onay bağlantısı iptal edildi")

        approval = await self.token_repo.get_approval(token)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")

        is_expired = datetime.now(UTC) > token.expires_at.replace(tzinfo=UTC)
        if is_expired and approval.status == ApprovalStatus.PENDING:
            raise HTTPException(status_code=410, detail="Bu onay bağlantısının süresi doldu")

        version_result = await self.db.execute(
            select(BriefVersion).where(BriefVersion.id == approval.version_id)
        )
        version = version_result.scalar_one_or_none()
        if not version:
            raise HTTPException(status_code=404, detail="Version snapshot not found")

        snapshot = version.snapshot
        brief_data = snapshot.get("brief", {})
        template_data = snapshot.get("template")
        sections_data = snapshot.get("sections", [])

        sections = []
        for sec in sections_data:
            fields = []
            for f in sec.get("fields", []):
                fields.append(
                    PublicFieldValue(
                        field_key=f.get("field_key", ""),
                        label=f.get("label", ""),
                        field_type=f.get("field_type", "text"),
                        is_required=f.get("is_required", False),
                        options=f.get("options"),
                        placeholder=f.get("placeholder"),
                        value=f.get("value"),
                    )
                )
            sections.append(
                PublicSection(
                    title=sec.get("title", ""),
                    description=sec.get("description"),
                    fields=fields,
                )
            )

        comments = await self.comment_repo.list_for_approval(approval.id, include_internal=False)

        return PublicApprovalView(
            approval_id=approval.id,
            status=approval.status,
            brief_title=brief_data.get("title", ""),
            brief_description=brief_data.get("description"),
            brief_priority=brief_data.get("priority", "normal"),
            brief_deadline=brief_data.get("deadline"),
            brand_name=snapshot.get("brand_name"),
            template_name=template_data.get("name") if template_data else None,
            version_number=version.version_number,
            sections=sections,
            comments=[ApprovalCommentRead.model_validate(c) for c in comments],
            expires_at=token.expires_at,
            decided_at=approval.decided_at,
        )

    async def approve(self, raw_token: str, payload: PublicApproveRequest) -> dict[str, str]:
        token, approval = await self._resolve_token(raw_token)
        now = datetime.now(UTC)

        await self.token_repo.update(token, {"used_at": now})
        await self.approval_repo.update(
            approval,
            {
                "status": ApprovalStatus.APPROVED,
                "approved_by_email": payload.approver_email,
                "approved_by_name": payload.approver_name,
                "decided_at": now,
            },
        )

        brief_result = await self.db.execute(
            select(BriefVersion.brief_id).where(BriefVersion.id == approval.version_id)
        )
        brief_id = brief_result.scalar_one_or_none()
        if brief_id:
            from app.models.brief import Brief

            b = await self.db.get(Brief, brief_id)
            if b:
                b.status = BriefStatus.APPROVED
                await self.db.flush()

        await self.event_repo.create(
            {
                "approval_id": approval.id,
                "event_type": "approved",
                "actor_type": "public_reviewer",
                "actor_email": payload.approver_email,
                "event_metadata": {"approver_name": payload.approver_name},
            }
        )

        await self.db.commit()

        # Notify agency members of public approval decision
        try:
            from app.models.agency_member import AgencyMember
            from app.models.enums import NotificationEventType
            from app.services.notification_dispatcher import NotificationDispatcher

            if brief_id:
                b_notify = await self.db.get(Brief, brief_id)
                if b_notify:
                    rows = await self.db.execute(
                        select(AgencyMember.user_id).where(
                            AgencyMember.agency_id == b_notify.agency_id,
                            AgencyMember.deleted_at.is_(None),
                        )
                    )
                    recipient_ids = [r[0] for r in rows]
                    if recipient_ids:
                        dispatcher = NotificationDispatcher(self.db)
                        await dispatcher.emit(
                            NotificationEventType.PUBLIC_APPROVAL_APPROVED.value,
                            payload={
                                "brief_id": str(brief_id),
                                "brief_title": b_notify.title or "",
                                "approver_name": payload.approver_name or "",
                                "approver_email": payload.approver_email or "",
                            },
                            agency_id=b_notify.agency_id,
                            brand_id=None,
                            actor_user_id=None,
                            recipient_ids=recipient_ids,
                        )
        except Exception:
            pass

        return {"message": "Brief onaylandı"}

    async def request_revision(
        self, raw_token: str, payload: PublicRevisionRequest
    ) -> dict[str, str]:
        token, approval = await self._resolve_token(raw_token)
        now = datetime.now(UTC)

        await self.comment_repo.create(
            {
                "approval_id": approval.id,
                "author_name": payload.approver_name,
                "author_email": payload.approver_email,
                "comment": payload.comment,
                "is_internal": False,
            }
        )

        await self.token_repo.update(token, {"used_at": now})
        await self.approval_repo.update(
            approval,
            {
                "status": ApprovalStatus.REVISION_REQUESTED,
                "approved_by_email": payload.approver_email,
                "approved_by_name": payload.approver_name,
                "decided_at": now,
            },
        )

        brief_result = await self.db.execute(
            select(BriefVersion.brief_id).where(BriefVersion.id == approval.version_id)
        )
        brief_id = brief_result.scalar_one_or_none()
        if brief_id:
            from app.models.brief import Brief

            b = await self.db.get(Brief, brief_id)
            if b:
                b.status = BriefStatus.REVISION_REQUESTED
                await self.db.flush()

        await self.event_repo.create(
            {
                "approval_id": approval.id,
                "event_type": "revision_requested",
                "actor_type": "public_reviewer",
                "actor_email": payload.approver_email,
                "event_metadata": {"approver_name": payload.approver_name},
            }
        )

        await self.db.commit()

        # Notify agency members of public revision request
        try:
            from app.models.agency_member import AgencyMember
            from app.models.enums import NotificationEventType
            from app.services.notification_dispatcher import NotificationDispatcher

            if brief_id:
                b_notify = await self.db.get(Brief, brief_id)
                if b_notify:
                    rows = await self.db.execute(
                        select(AgencyMember.user_id).where(
                            AgencyMember.agency_id == b_notify.agency_id,
                            AgencyMember.deleted_at.is_(None),
                        )
                    )
                    recipient_ids = [r[0] for r in rows]
                    if recipient_ids:
                        dispatcher = NotificationDispatcher(self.db)
                        await dispatcher.emit(
                            NotificationEventType.PUBLIC_APPROVAL_REVISION_REQUESTED.value,
                            payload={
                                "brief_id": str(brief_id),
                                "brief_title": b_notify.title or "",
                                "approver_name": payload.approver_name or "",
                                "approver_email": payload.approver_email or "",
                                "comment": payload.comment or "",
                            },
                            agency_id=b_notify.agency_id,
                            brand_id=None,
                            actor_user_id=None,
                            recipient_ids=recipient_ids,
                        )
        except Exception:
            pass

        return {"message": "Revizyon talebi alındı"}

    async def add_comment(
        self, raw_token: str, payload: AddPublicCommentRequest
    ) -> ApprovalCommentRead:
        token_hash = _hash_token(raw_token)
        token = await self.token_repo.get_by_hash(token_hash)
        if not token:
            raise HTTPException(status_code=404, detail="Approval link not found")
        if token.revoked_at is not None:
            raise HTTPException(status_code=410, detail="This approval link has been revoked")
        if datetime.now(UTC) > token.expires_at.replace(tzinfo=UTC):
            raise HTTPException(status_code=410, detail="This approval link has expired")

        approval = await self.token_repo.get_approval(token)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")

        comment = await self.comment_repo.create(
            {
                "approval_id": approval.id,
                "author_name": payload.author_name,
                "author_email": payload.author_email,
                "comment": payload.comment,
                "is_internal": False,
            }
        )
        await self.db.commit()
        return ApprovalCommentRead.model_validate(comment)

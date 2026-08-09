from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WhatsAppTemplateStatus
from app.models.template import WhatsAppTemplate


class WhatsAppTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_code(self, code: str) -> WhatsAppTemplate | None:
        stmt = select(WhatsAppTemplate).where(
            WhatsAppTemplate.code == code,
            WhatsAppTemplate.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_approved(
        self,
        code: str,
        locale: str = "tr",
        provider: str = "twilio",
    ) -> WhatsAppTemplate | None:
        """Return the template only if it is approved, has a content_sid, and
        matches provider/locale. Returns None for any other reason (missing,
        draft, pending, rejected, disabled, no content_sid) — callers must not
        distinguish further; "not usable" is "not usable"."""
        template = await self.get_by_code(code)
        if template is None:
            return None
        if template.status != WhatsAppTemplateStatus.APPROVED.value:
            return None
        if not template.content_sid:
            return None
        if template.provider != provider:
            return None
        if template.language_code != locale:
            return None
        return template

    async def list_all(self) -> list[WhatsAppTemplate]:
        stmt = select(WhatsAppTemplate).where(WhatsAppTemplate.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_approval(
        self,
        template: WhatsAppTemplate,
        status: str,
        content_sid: str | None,
        updated_by_id: uuid.UUID,
    ) -> WhatsAppTemplate:
        status_changed = template.status != status
        content_sid_changed = content_sid is not None and template.content_sid != content_sid

        template.status = status
        if content_sid is not None:
            template.content_sid = content_sid
        template.updated_by_id = updated_by_id
        if status == WhatsAppTemplateStatus.APPROVED.value:
            template.approved_at = datetime.now(UTC)
        if status_changed or content_sid_changed:
            # A queued/pending WhatsApp retry snapshots `revision` at send
            # time (see NotificationDelivery.template_revision) — bumping it
            # here is what lets that retry detect the template it was built
            # against no longer matches and refuse to fire a stale send.
            template.revision += 1
        self.session.add(template)
        await self.session.flush()
        await self.session.refresh(template)
        return template

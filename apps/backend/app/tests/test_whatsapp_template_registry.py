"""Tests for the WhatsApp approved-template registry (WhatsAppTemplateRepository)."""

from __future__ import annotations

import uuid

import pytest

from app.db.session import AsyncSessionLocal
from app.models.enums import WhatsAppTemplateStatus
from app.models.template import WhatsAppTemplate
from app.repositories.whatsapp_template import WhatsAppTemplateRepository


@pytest.fixture
async def draft_template():
    code = f"test_tpl_{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as session:
        row = WhatsAppTemplate(
            id=uuid.uuid4(),
            code=code,
            event_type="system.test_notification",
            provider="twilio",
            template_name="Test Template",
            language_code="tr",
            content_sid=None,
            status=WhatsAppTemplateStatus.DRAFT.value,
            variable_schema={},
            body="Test body",
        )
        session.add(row)
        await session.commit()
        try:
            yield code
        finally:
            obj = await session.get(WhatsAppTemplate, row.id)
            if obj is not None:
                await session.delete(obj)
                await session.commit()


class TestWhatsAppTemplateRepository:
    async def test_seeded_test_template_exists(self) -> None:
        async with AsyncSessionLocal() as session:
            repo = WhatsAppTemplateRepository(session)
            template = await repo.get_by_code("flobrief_test_notification")
        assert template is not None
        assert template.event_type == "system.test_notification"

    async def test_get_approved_returns_none_for_missing_code(self) -> None:
        async with AsyncSessionLocal() as session:
            repo = WhatsAppTemplateRepository(session)
            result = await repo.get_approved("does_not_exist_" + uuid.uuid4().hex)
        assert result is None

    async def test_get_approved_returns_none_for_draft_status(self, draft_template) -> None:
        async with AsyncSessionLocal() as session:
            repo = WhatsAppTemplateRepository(session)
            result = await repo.get_approved(draft_template)
        assert result is None

    async def test_get_approved_returns_none_without_content_sid(self, draft_template) -> None:
        async with AsyncSessionLocal() as session:
            repo = WhatsAppTemplateRepository(session)
            template = await repo.get_by_code(draft_template)
            await repo.update_approval(
                template,
                status=WhatsAppTemplateStatus.APPROVED.value,
                content_sid=None,
                updated_by_id=None,
            )
            result = await repo.get_approved(draft_template)
        assert result is None

    async def test_get_approved_returns_template_when_approved_with_content_sid(
        self, draft_template
    ) -> None:
        async with AsyncSessionLocal() as session:
            repo = WhatsAppTemplateRepository(session)
            template = await repo.get_by_code(draft_template)
            await repo.update_approval(
                template,
                status=WhatsAppTemplateStatus.APPROVED.value,
                content_sid="HXapproved123",
                updated_by_id=None,
            )
            result = await repo.get_approved(draft_template)
        assert result is not None
        assert result.content_sid == "HXapproved123"
        assert result.approved_at is not None

    async def test_get_approved_rejects_wrong_locale(self, draft_template) -> None:
        async with AsyncSessionLocal() as session:
            repo = WhatsAppTemplateRepository(session)
            template = await repo.get_by_code(draft_template)
            await repo.update_approval(
                template,
                status=WhatsAppTemplateStatus.APPROVED.value,
                content_sid="HXapproved123",
                updated_by_id=None,
            )
            result = await repo.get_approved(draft_template, locale="en")
        assert result is None

    async def test_get_approved_rejects_disabled_status(self, draft_template) -> None:
        async with AsyncSessionLocal() as session:
            repo = WhatsAppTemplateRepository(session)
            template = await repo.get_by_code(draft_template)
            await repo.update_approval(
                template,
                status=WhatsAppTemplateStatus.DISABLED.value,
                content_sid="HXapproved123",
                updated_by_id=None,
            )
            result = await repo.get_approved(draft_template)
        assert result is None

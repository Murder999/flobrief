"""Centralized WhatsApp message template renderer.

All message strings live here — no raw strings scattered across the codebase.
Sensitive fields (internal notes, full comment body, agency-internal data)
are excluded. Action URLs are built via UrlBuilder using FRONTEND_PUBLIC_URL.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.services.url_builder import url_builder


class WhatsAppTemplateService:
    @staticmethod
    def brief_created(
        brand_name: str,
        brief_title: str,
        deadline: datetime | None,
        brief_id: uuid.UUID,
    ) -> str:
        deadline_str = deadline.strftime("%d %B %Y") if deadline else "—"
        action = url_builder.brief_detail(brief_id)
        return (
            f"📋 PostPiloter — Yeni Brief\n\n"
            f"Marka: {brand_name}\n"
            f"Brief: {brief_title}\n"
            f"Teslim: {deadline_str}\n\n"
            f"Görüntüle:\n{action}"
        )

    @staticmethod
    def brief_assigned(brief_title: str, brief_id: uuid.UUID) -> str:
        action = url_builder.brief_detail(brief_id)
        return (
            f"📌 PostPiloter — Brief Atandı\n\n" f"Brief: {brief_title}\n\n" f"Görüntüle:\n{action}"
        )

    @staticmethod
    def brand_brief_submitted(brief_title: str, brief_id: uuid.UUID) -> str:
        action = url_builder.brand_brief_detail(brief_id)
        return (
            f"📤 PostPiloter — Brief Gönderildi\n\n"
            f"Brief: {brief_title}\n\n"
            f"Görüntüle:\n{action}"
        )

    @staticmethod
    def comment_created(brief_title: str, comment_preview: str, brief_id: uuid.UUID) -> str:
        preview = comment_preview[:100] + "…" if len(comment_preview) > 100 else comment_preview
        action = url_builder.brief_detail(brief_id)
        return (
            f"💬 PostPiloter — Yeni Yorum\n\n"
            f"Brief: {brief_title}\n"
            f"Yorum: {preview}\n\n"
            f"Görüntüle:\n{action}"
        )

    @staticmethod
    def revision_requested(brief_title: str, brief_id: uuid.UUID) -> str:
        action = url_builder.brief_detail(brief_id)
        return (
            f"🔄 PostPiloter — Revizyon İstendi\n\n"
            f"Brief: {brief_title}\n\n"
            f"Görüntüle:\n{action}"
        )

    @staticmethod
    def approval_requested(brief_title: str, brief_id: uuid.UUID) -> str:
        action = url_builder.brief_detail(brief_id)
        return (
            f"⏳ PostPiloter — Onay Bekleniyor\n\n"
            f"Brief: {brief_title}\n\n"
            f"Onaya git:\n{action}"
        )

    @staticmethod
    def approval_approved(brief_title: str, brief_id: uuid.UUID) -> str:
        action = url_builder.brief_detail(brief_id)
        return (
            f"✅ PostPiloter — Brief Onaylandı\n\n"
            f"Brief: {brief_title}\n\n"
            f"Görüntüle:\n{action}"
        )

    @staticmethod
    def approval_rejected(brief_title: str, brief_id: uuid.UUID) -> str:
        action = url_builder.brief_detail(brief_id)
        return (
            f"❌ PostPiloter — Brief Reddedildi\n\n"
            f"Brief: {brief_title}\n\n"
            f"Görüntüle:\n{action}"
        )

    @staticmethod
    def file_uploaded(brief_title: str, file_name: str, brief_id: uuid.UUID) -> str:
        action = url_builder.brief_detail(brief_id)
        return (
            f"📎 PostPiloter — Dosya Yüklendi\n\n"
            f"Brief: {brief_title}\n"
            f"Dosya: {file_name}\n\n"
            f"Görüntüle:\n{action}"
        )

    @staticmethod
    def deadline_approaching(brief_title: str, deadline: datetime, brief_id: uuid.UUID) -> str:
        deadline_str = deadline.strftime("%d %B %Y")
        action = url_builder.brief_detail(brief_id)
        return (
            f"⚠️ PostPiloter — Teslim Tarihi Yaklaşıyor\n\n"
            f"Brief: {brief_title}\n"
            f"Teslim: {deadline_str}\n\n"
            f"Görüntüle:\n{action}"
        )

    @staticmethod
    def deadline_overdue(brief_title: str, deadline: datetime, brief_id: uuid.UUID) -> str:
        deadline_str = deadline.strftime("%d %B %Y")
        action = url_builder.brief_detail(brief_id)
        return (
            f"🚨 PostPiloter — Teslim Tarihi Geçti\n\n"
            f"Brief: {brief_title}\n"
            f"Teslim: {deadline_str}\n\n"
            f"Görüntüle:\n{action}"
        )

    @staticmethod
    def deliverable_submitted(brief_title: str, deliverable_title: str, brief_id: uuid.UUID) -> str:
        action = url_builder.brief_detail(brief_id)
        return (
            f"📦 PostPiloter — Yeni Teslimat\n\n"
            f"Brief: {brief_title}\n"
            f"Teslimat: {deliverable_title}\n\n"
            f"İncelemek için:\n{action}"
        )

    @staticmethod
    def deliverable_approved(brief_title: str, deliverable_title: str, brief_id: uuid.UUID) -> str:
        action = url_builder.brief_detail(brief_id)
        return (
            f"✅ PostPiloter — Teslimat Onaylandı\n\n"
            f"Brief: {brief_title}\n"
            f"Teslimat: {deliverable_title}\n\n"
            f"Görüntüle:\n{action}"
        )

    @staticmethod
    def deliverable_revision_requested(
        brief_title: str, deliverable_title: str, brief_id: uuid.UUID
    ) -> str:
        action = url_builder.brief_detail(brief_id)
        return (
            f"🔄 PostPiloter — Teslimat Revizyonu\n\n"
            f"Brief: {brief_title}\n"
            f"Teslimat: {deliverable_title}\n\n"
            f"Revizyon detayı:\n{action}"
        )

    @staticmethod
    def milestone_assigned(task_title: str, brief_title: str, brief_id: uuid.UUID) -> str:
        action = url_builder.brief_detail(brief_id)
        return (
            f"📌 PostPiloter — Görev Atandı\n\n"
            f"Görev: {task_title}\n"
            f"Brief: {brief_title}\n\n"
            f"Görüntüle:\n{action}"
        )

    @staticmethod
    def generic(title: str, body: str) -> str:
        return f"📣 PostPiloter — {title}\n\n{body}"


whatsapp_templates = WhatsAppTemplateService()

"""Centralized URL builder for action links in notifications.

Uses FRONTEND_PUBLIC_URL (set to ngrok/Cloudflare Tunnel in dev) so that
WhatsApp message links are reachable from phones outside localhost.
"""

from __future__ import annotations

import uuid
from urllib.parse import quote

from app.core.config import settings


def _base() -> str:
    return settings.FRONTEND_PUBLIC_URL.rstrip("/")


class UrlBuilder:
    @staticmethod
    def brief_detail(brief_id: uuid.UUID) -> str:
        return f"{_base()}/dashboard/briefs/{brief_id}"

    @staticmethod
    def brand_brief_detail(brief_id: uuid.UUID) -> str:
        return f"{_base()}/brand/briefs/{brief_id}"

    @staticmethod
    def brief_comments(brief_id: uuid.UUID, *, brand_side: bool = False) -> str:
        base_path = "brand/briefs" if brand_side else "dashboard/briefs"
        return f"{_base()}/{base_path}/{brief_id}?panel=comments"

    @staticmethod
    def deliverable_detail(
        brief_id: uuid.UUID, deliverable_id: uuid.UUID, *, brand_side: bool = False
    ) -> str:
        base_path = "brand/briefs" if brand_side else "dashboard/briefs"
        return f"{_base()}/{base_path}/{brief_id}?deliverable={deliverable_id}"

    @staticmethod
    def annotation_detail(
        brief_id: uuid.UUID,
        deliverable_id: uuid.UUID,
        annotation_id: uuid.UUID,
        *,
        brand_side: bool = False,
    ) -> str:
        base_path = "brand/briefs" if brand_side else "dashboard/briefs"
        return (
            f"{_base()}/{base_path}/{brief_id}"
            f"?deliverable={deliverable_id}&annotation={annotation_id}"
        )

    @staticmethod
    def invoice_detail(invoice_id: uuid.UUID, *, brand_side: bool = False) -> str:
        base_path = "brand/invoices" if brand_side else "dashboard/finance/invoices"
        return f"{_base()}/{base_path}/{invoice_id}"

    @staticmethod
    def approval_link(token: str) -> str:
        return f"{_base()}/approve/{token}"

    @staticmethod
    def invite_link(token: str) -> str:
        return f"{_base()}/invite/{quote(token, safe='')}"

    @staticmethod
    def partnership_invite_link(token: str) -> str:
        return f"{_base()}/partner-invite/{quote(token, safe='')}"

    @staticmethod
    def verification_link(token: str) -> str:
        return f"{_base()}/auth/verify-email?token={quote(token, safe='')}"

    @staticmethod
    def password_reset_link(token: str) -> str:
        return f"{_base()}/auth/reset-password?token={quote(token, safe='')}"

    @staticmethod
    def notification_preferences(*, brand_side: bool = False) -> str:
        base_path = "brand/notifications" if brand_side else "dashboard/settings/notifications"
        return f"{_base()}/{base_path}"


url_builder = UrlBuilder()

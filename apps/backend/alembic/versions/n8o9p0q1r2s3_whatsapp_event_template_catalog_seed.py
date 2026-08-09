"""whatsapp_event_template_catalog_seed

Part 6B-1 — WhatsApp domain event routing.

Idempotently seeds the whatsapp_templates registry with one draft row per
template_key referenced by app.services.whatsapp_event_catalog
(WHATSAPP_EVENT_CATALOG). Every row is created status=draft, content_sid=NULL
— an operator must register a real Meta/Twilio-approved Content Template and
flip status to approved before NotificationDispatcher will ever send it (see
WhatsAppTemplateRepository.get_approved). Until then, the matching domain
event's WhatsApp delivery records skipped_template_missing while in-app/
email continue unaffected — never a freeform fallback for a real domain
event (that path is Part 6A's dev-only Sandbox test-send flow only).

`code` is UNIQUE, so a second run of this migration (impossible under normal
alembic operation, since a revision only ever applies once, but relevant if
someone hand-rolls the same insert) would fail loudly rather than silently
duplicating rows — the same idempotency contract the Part 6A seed already
relies on.

Revision ID: n8o9p0q1r2s3
Revises: f3g4h5i6j7k8
Create Date: 2026-07-28 00:00:00.000000
"""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n8o9p0q1r2s3"
down_revision: Union[str, None] = "f3g4h5i6j7k8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.dialects.postgresql.JSONB
UUID = sa.dialects.postgresql.UUID

# (code, event_type, template_name, body)
# body is a human-readable reference of the intended Twilio Content Template
# copy — never sent as-is (drafts never reach send_template_message); the
# real approved body/variable order lives in Twilio's Content API once an
# operator registers it, at which point variable_schema is filled in to map
# Twilio's {{n}} placeholders to the allowlisted field names in
# app.services.whatsapp_payload_builder.ALLOWED_VARIABLE_FIELDS.
_SEED_TEMPLATES: list[tuple[str, str, str, str]] = [
    (
        "brief_created",
        "brief.created",
        "Brief Oluşturuldu",
        "Merhaba {{1}}, {{2}} markası için yeni bir brief oluşturuldu: {{3}}. Detay: {{4}}",
    ),
    (
        "brief_assigned",
        "brief.assigned",
        "Brief Atandı",
        "Merhaba {{1}}, '{{2}}' briefine atandınız. Detay: {{3}}",
    ),
    (
        "comment_added",
        "comment.added",
        "Yeni Yorum",
        "Merhaba {{1}}, {{2}} '{{3}}' briefine yorum yaptı: {{4}}. Detay: {{5}}",
    ),
    (
        "mention_created",
        "mention.in_comment",
        "Bahsedildiniz",
        "Merhaba {{1}}, {{2}} sizi '{{3}}' briefinde etiketledi. Detay: {{4}}",
    ),
    (
        "deliverable_submitted",
        "deliverable.submitted",
        "Yeni Teslimat",
        "Merhaba {{1}}, '{{2}}' briefi için yeni bir teslimat inceleminizi bekliyor: {{3}}. Detay: {{4}}",
    ),
    (
        "approval_requested",
        "brief.submitted_for_approval",
        "Onay Bekleniyor",
        "Merhaba {{1}}, '{{2}}' briefi onayınızı bekliyor. Detay: {{3}}",
    ),
    (
        "deliverable_approved",
        "deliverable.approved",
        "Teslimat Onaylandı",
        "Merhaba {{1}}, '{{2}}' briefindeki '{{3}}' teslimatı onaylandı. Detay: {{4}}",
    ),
    (
        "revision_requested",
        "brief.revision_requested",
        "Revizyon İstendi",
        "Merhaba {{1}}, '{{2}}' için revizyon talep edildi. Özet: {{3}}. Detay: {{4}}",
    ),
    (
        "annotation_created",
        "annotation.created",
        "Yeni Revizyon Notu",
        "Merhaba {{1}}, '{{2}}' üzerinde yeni bir revizyon notu eklendi. Detay: {{3}}",
    ),
    (
        "annotation_replied",
        "annotation.replied",
        "Revizyon Notuna Yanıt",
        "Merhaba {{1}}, '{{2}}' üzerindeki bir revizyon notuna yanıt geldi. Detay: {{3}}",
    ),
    (
        "brief_due_soon",
        "calendar.item_due",
        "Teslim Tarihi Yaklaşıyor",
        "Merhaba {{1}}, '{{2}}' briefinin teslim tarihi yaklaşıyor: {{3}}. Detay: {{4}}",
    ),
    (
        "brief_overdue",
        "brief.overdue",
        "Teslim Tarihi Geçti",
        "Merhaba {{1}}, '{{2}}' briefinin teslim tarihi geçti: {{3}}. Detay: {{4}}",
    ),
    (
        "invoice_sent",
        "invoice.sent",
        "Fatura Gönderildi",
        "Merhaba {{1}}, {{2}} numaralı fatura size gönderildi. Vade: {{3}}. Detay: {{4}}",
    ),
    (
        "invoice_due_soon",
        "invoice.due_soon",
        "Fatura Vadesi Yaklaşıyor",
        "Merhaba {{1}}, {{2}} numaralı faturanın vadesi yaklaşıyor: {{3}}. Detay: {{4}}",
    ),
    (
        "invoice_overdue",
        "invoice.overdue",
        "Fatura Vadesi Geçti",
        "Merhaba {{1}}, {{2}} numaralı faturanın vadesi geçti: {{3}}. Detay: {{4}}",
    ),
    (
        "invoice_payment_received",
        "invoice.payment_received",
        "Ödeme Alındı",
        "Merhaba {{1}}, {{2}} numaralı fatura için ödeme alındı: {{3}}. Detay: {{4}}",
    ),
]


_whatsapp_templates_table = sa.table(
    "whatsapp_templates",
    sa.column("id", UUID(as_uuid=True)),
    sa.column("code", sa.String),
    sa.column("event_type", sa.String),
    sa.column("provider", sa.String),
    sa.column("template_name", sa.String),
    sa.column("language_code", sa.String),
    sa.column("content_sid", sa.String),
    sa.column("status", sa.String),
    sa.column("variable_schema", JSONB),
    sa.column("body", sa.Text),
)


def upgrade() -> None:
    whatsapp_templates_table = _whatsapp_templates_table
    op.bulk_insert(
        whatsapp_templates_table,
        [
            {
                "id": _uuid.uuid4(),
                "code": code,
                "event_type": event_type,
                "provider": "twilio",
                "template_name": template_name,
                "language_code": "tr",
                "content_sid": None,
                "status": "draft",
                "variable_schema": {},
                "body": body,
            }
            for code, event_type, template_name, body in _SEED_TEMPLATES
        ],
    )


def downgrade() -> None:
    codes = [code for code, _event_type, _name, _body in _SEED_TEMPLATES]
    op.execute(_whatsapp_templates_table.delete().where(_whatsapp_templates_table.c.code.in_(codes)))

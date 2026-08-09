"""Owner/Admin WhatsApp management-center read models (Part 6B-2).

Every function here is read-only and tenant-scoped by an explicit
`agency_id` argument — none of them accept a caller-supplied recipient,
content_sid, or approval action (approving a template and setting its real
Content SID remain platform_admin-only via whatsapp_template_service /
platform notification-providers routes, untouched by this module). Nothing
here ever returns a raw secret, a full phone number, or a raw provider
response.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency_member import AgencyMember
from app.models.enums import AgencyMemberStatus, WhatsAppTemplateStatus
from app.models.notification import NotificationPreference
from app.models.platform_provider_settings import PlatformProviderSetting
from app.models.template import WhatsAppTemplate
from app.models.user import User
from app.repositories.notification import NotificationDeliveryRepository
from app.repositories.whatsapp_template import WhatsAppTemplateRepository
from app.services.whatsapp_connection_status import compute_connection_status
from app.services.whatsapp_event_catalog import WHATSAPP_EVENT_CATALOG
from app.services.whatsapp_payload_builder import ALLOWED_VARIABLE_FIELDS
from app.services.whatsapp_preference_service import WHATSAPP_EVENT_UI_CATALOG

_WHATSAPP_PROVIDER_ROW = "whatsapp_twilio"


@dataclass(frozen=True)
class WhatsAppAgencySummary:
    connection_status: str
    sender_masked: str | None
    environment: str
    opted_in_users: int
    whatsapp_enabled_users: int
    templates_ready: int
    templates_not_ready: int
    deliveries_24h: dict[str, int]
    deliveries_7d: dict[str, int]
    last_safe_error: str | None
    demo_tenant: bool
    # Part 6B-3
    retry_queue: int
    retry_exhausted: int
    delivery_success_rate_7d: float | None
    read_rate_7d: float | None
    top_failure_category_7d: str | None


async def build_agency_summary(
    db: AsyncSession, *, agency_id: uuid.UUID, is_demo: bool
) -> WhatsAppAgencySummary:
    provider_row = await db.scalar(
        select(PlatformProviderSetting).where(
            PlatformProviderSetting.provider == _WHATSAPP_PROVIDER_ROW,
            PlatformProviderSetting.deleted_at.is_(None),
        )
    )
    connection_status = compute_connection_status(provider_row)

    opted_in_users = await db.scalar(
        select(func.count(func.distinct(User.id)))
        .select_from(User)
        .join(AgencyMember, AgencyMember.user_id == User.id)
        .where(
            AgencyMember.agency_id == agency_id,
            AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
            AgencyMember.deleted_at.is_(None),
            User.whatsapp_opt_in.is_(True),
        )
    ) or 0

    whatsapp_enabled_users = await db.scalar(
        select(func.count(func.distinct(User.id)))
        .select_from(User)
        .join(AgencyMember, AgencyMember.user_id == User.id)
        .join(NotificationPreference, NotificationPreference.user_id == User.id)
        .where(
            AgencyMember.agency_id == agency_id,
            AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
            AgencyMember.deleted_at.is_(None),
            NotificationPreference.whatsapp_enabled.is_(True),
        )
    ) or 0

    catalog_codes = {defn.template_key for defn in WHATSAPP_EVENT_CATALOG.values()}
    template_rows = await db.execute(
        select(WhatsAppTemplate.code, WhatsAppTemplate.status, WhatsAppTemplate.content_sid).where(
            WhatsAppTemplate.deleted_at.is_(None)
        )
    )
    templates_ready = 0
    templates_not_ready = 0
    seen_codes: set[str] = set()
    for code, status_val, content_sid in template_rows.all():
        if code not in catalog_codes:
            continue
        seen_codes.add(code)
        if status_val == WhatsAppTemplateStatus.APPROVED.value and content_sid:
            templates_ready += 1
        else:
            templates_not_ready += 1
    templates_not_ready += len(catalog_codes - seen_codes)

    delivery_repo = NotificationDeliveryRepository(db)
    now = datetime.now(UTC)
    deliveries_24h = await delivery_repo.summary_counts_for_agency(
        agency_id, since=now - timedelta(hours=24)
    )
    deliveries_7d = await delivery_repo.summary_counts_for_agency(
        agency_id, since=now - timedelta(days=7)
    )
    last_error_row = await delivery_repo.latest_error_for_agency(agency_id)
    retry_metrics = await delivery_repo.retry_metrics_for_agency(agency_id)
    top_failure_category = await delivery_repo.top_failure_category_for_agency(
        agency_id, since=now - timedelta(days=7)
    )

    _SUCCESS_STATUSES = ("sent", "delivered", "read")  # noqa: N806
    _ATTEMPTED_STATUSES = ("sent", "delivered", "read", "failed")  # noqa: N806
    attempted = sum(deliveries_7d.get(s, 0) for s in _ATTEMPTED_STATUSES)
    successful = sum(deliveries_7d.get(s, 0) for s in _SUCCESS_STATUSES)
    delivery_success_rate = (successful / attempted) if attempted > 0 else None

    delivered_or_read = deliveries_7d.get("delivered", 0) + deliveries_7d.get("read", 0)
    read_rate = (
        (deliveries_7d.get("read", 0) / delivered_or_read) if delivered_or_read > 0 else None
    )

    return WhatsAppAgencySummary(
        connection_status=connection_status,
        sender_masked=provider_row.whatsapp_from_masked if provider_row else None,
        environment="production" if connection_status == "connected" else "sandbox",
        opted_in_users=opted_in_users,
        whatsapp_enabled_users=whatsapp_enabled_users,
        templates_ready=templates_ready,
        templates_not_ready=templates_not_ready,
        deliveries_24h=deliveries_24h,
        deliveries_7d=deliveries_7d,
        last_safe_error=last_error_row.error_message if last_error_row else None,
        demo_tenant=is_demo,
        retry_queue=retry_metrics["retry_queue"],
        retry_exhausted=retry_metrics["retry_exhausted"],
        delivery_success_rate_7d=delivery_success_rate,
        read_rate_7d=read_rate,
        top_failure_category_7d=top_failure_category,
    )


@dataclass(frozen=True)
class WhatsAppTemplateMatrixRow:
    event_type: str
    event_label: str
    template_key: str
    locale: str
    status: str
    enabled: bool
    has_content_sid: bool
    approved_at: datetime | None
    recipient_policy: str


async def build_template_matrix(db: AsyncSession) -> list[WhatsAppTemplateMatrixRow]:
    template_repo = WhatsAppTemplateRepository(db)
    templates_by_code = {t.code: t for t in await template_repo.list_all()}

    rows: list[WhatsAppTemplateMatrixRow] = []
    for event_type, defn in WHATSAPP_EVENT_CATALOG.items():
        ui_meta = WHATSAPP_EVENT_UI_CATALOG.get(event_type)
        template = templates_by_code.get(defn.template_key)
        rows.append(
            WhatsAppTemplateMatrixRow(
                event_type=event_type,
                event_label=ui_meta.label if ui_meta else event_type,
                template_key=defn.template_key,
                locale=template.language_code if template else defn.locale_fallback,
                status=template.status if template else WhatsAppTemplateStatus.DRAFT.value,
                enabled=bool(template and template.status != WhatsAppTemplateStatus.DISABLED.value),
                has_content_sid=bool(template and template.content_sid),
                approved_at=template.approved_at if template else None,
                recipient_policy=defn.recipient_policy,
            )
        )
    return rows


@dataclass(frozen=True)
class WhatsAppTemplatePreview:
    event_type: str
    event_label: str
    template_key: str
    locale: str
    status: str
    sample_message: str
    variable_names: list[str]
    recipient_roles: str
    sensitive_data_note: str


_SAMPLE_VARS = {
    "recipient_first_name": "Ayşe",
    "actor_display_name": "Mehmet",
    "brief_title": "Yeni Kampanya Briefi",
    "brand_name": "Örnek Marka",
    "deliverable_title": "Instagram Görsel Seti",
    "due_date": "15 Ağustos",
    "invoice_number": "INV-2026-001",
    "invoice_total_formatted": "12.500,00 TRY",
    "short_safe_summary": "Yeni bir güncelleme var.",
    "deep_link_url": "https://app.flobrief.com/...",
}

_SAMPLE_TEMPLATES: dict[str, str] = {
    "brief_created": (
        "Merhaba {recipient_first_name}, '{brief_title}' için yeni bir brief oluşturuldu."
    ),
    "brief_assigned": "Merhaba {recipient_first_name}, '{brief_title}' briefi size atandı.",
    "comment_added": "{actor_display_name}, '{brief_title}' briefine yeni bir yorum ekledi.",
    "mention_created": "{actor_display_name} sizi bir yorumda etiketledi: '{brief_title}'.",
    "deliverable_submitted": (
        "'{brand_name}' için yeni bir teslimat incelemenizi bekliyor: {deliverable_title}."
    ),
    "approval_requested": "Merhaba {recipient_first_name}, '{brief_title}' onayınızı bekliyor.",
    "deliverable_approved": "'{deliverable_title}' teslimatı {brand_name} tarafından onaylandı.",
    "revision_requested": "'{brief_title}' için revizyon istendi.",
    "annotation_created": "'{deliverable_title}' üzerinde yeni bir revizyon notu eklendi.",
    "annotation_replied": "Revizyon notunuza bir yanıt geldi.",
    "brief_due_soon": "'{brief_title}' teslim tarihi yaklaşıyor: {due_date}.",
    "brief_overdue": "'{brief_title}' teslim tarihi geçti.",
    "invoice_sent": "'{brand_name}' için yeni bir fatura gönderildi: {invoice_number}.",
    "invoice_due_soon": "{invoice_number} numaralı faturanızın vadesi yaklaşıyor: {due_date}.",
    "invoice_overdue": "{invoice_number} numaralı faturanın vadesi geçti.",
    "invoice_payment_received": (
        "{invoice_number} numaralı fatura için ödeme alındı: {invoice_total_formatted}."
    ),
}


def build_template_preview(event_type: str) -> WhatsAppTemplatePreview | None:
    defn = WHATSAPP_EVENT_CATALOG.get(event_type)
    ui_meta = WHATSAPP_EVENT_UI_CATALOG.get(event_type)
    if defn is None or ui_meta is None:
        return None

    raw = _SAMPLE_TEMPLATES.get(
        defn.template_key, "Merhaba {recipient_first_name}, yeni bir güncelleme var."
    )
    try:
        sample_message = raw.format(**_SAMPLE_VARS)
    except (KeyError, IndexError):  # pragma: no cover - defensive
        sample_message = raw

    return WhatsAppTemplatePreview(
        event_type=event_type,
        event_label=ui_meta.label,
        template_key=defn.template_key,
        locale=defn.locale_fallback,
        status="preview_only",
        sample_message=sample_message,
        variable_names=sorted(ALLOWED_VARIABLE_FIELDS),
        recipient_roles=defn.recipient_policy,
        sensitive_data_note=(
            "Bu önizleme örnek/placeholder verilerle oluşturulur; gerçek kullanıcı, "
            "marka veya müşteri verisi hiçbir zaman gösterilmez."
        ),
    )

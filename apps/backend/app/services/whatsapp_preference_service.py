"""Role-aware WhatsApp event-preference grouping (Part 6B-2).

The authoritative list of WhatsApp-eligible events is
`whatsapp_event_catalog.WHATSAPP_EVENT_CATALOG` — an event with no catalog
entry has no WhatsApp channel at all and is never shown here (showing a
toggle for an event that can never send would be a fake control). This
module only adds *UI* metadata on top of that catalog: which group an event
belongs to, which portal(s) see it, and which permission (if any) is
required — enforced both when building the list (backend) and expected to be
mirrored by hiding the control client-side.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import (
    Permission,
    get_permissions_for_agency_role,
    get_permissions_for_brand_role,
)
from app.models.agency_member import AgencyMember
from app.models.brand_member import BrandMember
from app.models.enums import (
    AgencyMemberStatus,
    BrandMemberStatus,
    NotificationEventType,
    UserType,
)
from app.models.user import User
from app.services.whatsapp_event_catalog import WHATSAPP_EVENT_CATALOG

EVENT_GROUP_BUSINESS = "brief_and_work"
EVENT_GROUP_COLLABORATION = "comments_and_collaboration"
EVENT_GROUP_DELIVERY = "delivery_and_approval"
EVENT_GROUP_FINANCE = "finance"

EVENT_GROUP_LABELS: dict[str, str] = {
    EVENT_GROUP_BUSINESS: "İş ve Brief",
    EVENT_GROUP_COLLABORATION: "Yorum ve İş Birliği",
    EVENT_GROUP_DELIVERY: "Teslim ve Onay",
    EVENT_GROUP_FINANCE: "Finans",
}

_AGENCY = "agency"
_BRAND = "brand"


@dataclass(frozen=True)
class WhatsAppEventUIMeta:
    event_type: str
    group: str
    label: str
    portals: frozenset[str]
    required_permission: Permission | None = None


WHATSAPP_EVENT_UI_CATALOG: dict[str, WhatsAppEventUIMeta] = {
    NotificationEventType.BRIEF_CREATED.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.BRIEF_CREATED.value,
        group=EVENT_GROUP_BUSINESS,
        label="Yeni brief oluşturuldu",
        portals=frozenset({_AGENCY}),
    ),
    NotificationEventType.BRIEF_ASSIGNED.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.BRIEF_ASSIGNED.value,
        group=EVENT_GROUP_BUSINESS,
        label="Brief size atandı",
        portals=frozenset({_AGENCY}),
    ),
    NotificationEventType.CALENDAR_ITEM_DUE.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.CALENDAR_ITEM_DUE.value,
        group=EVENT_GROUP_BUSINESS,
        label="Teslim tarihi yaklaşıyor",
        portals=frozenset({_AGENCY}),
    ),
    NotificationEventType.BRIEF_OVERDUE.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.BRIEF_OVERDUE.value,
        group=EVENT_GROUP_BUSINESS,
        label="Brief tarihi geçti",
        portals=frozenset({_AGENCY}),
    ),
    NotificationEventType.COMMENT_ADDED.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.COMMENT_ADDED.value,
        group=EVENT_GROUP_COLLABORATION,
        label="Yeni yorum eklendi",
        portals=frozenset({_AGENCY, _BRAND}),
    ),
    NotificationEventType.MENTIONED_IN_COMMENT.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.MENTIONED_IN_COMMENT.value,
        group=EVENT_GROUP_COLLABORATION,
        label="Bir yorumda etiketlendiniz",
        portals=frozenset({_AGENCY, _BRAND}),
    ),
    NotificationEventType.MENTIONED_IN_ANNOTATION.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.MENTIONED_IN_ANNOTATION.value,
        group=EVENT_GROUP_COLLABORATION,
        label="Bir revizyon notunda etiketlendiniz",
        portals=frozenset({_AGENCY, _BRAND}),
    ),
    NotificationEventType.ANNOTATION_CREATED.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.ANNOTATION_CREATED.value,
        group=EVENT_GROUP_COLLABORATION,
        label="Yeni revizyon notu eklendi",
        portals=frozenset({_AGENCY, _BRAND}),
    ),
    NotificationEventType.ANNOTATION_REPLIED.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.ANNOTATION_REPLIED.value,
        group=EVENT_GROUP_COLLABORATION,
        label="Revizyon notuna yanıt geldi",
        portals=frozenset({_AGENCY, _BRAND}),
    ),
    NotificationEventType.DELIVERABLE_SUBMITTED.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.DELIVERABLE_SUBMITTED.value,
        group=EVENT_GROUP_DELIVERY,
        label="Yeni teslimat incelemenizi bekliyor",
        portals=frozenset({_BRAND}),
    ),
    NotificationEventType.BRIEF_SUBMITTED.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.BRIEF_SUBMITTED.value,
        group=EVENT_GROUP_DELIVERY,
        label="Onayınız bekleniyor",
        portals=frozenset({_BRAND}),
        required_permission=Permission.BRIEF_APPROVE,
    ),
    NotificationEventType.DELIVERABLE_APPROVED.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.DELIVERABLE_APPROVED.value,
        group=EVENT_GROUP_DELIVERY,
        label="Teslimat onaylandı",
        portals=frozenset({_AGENCY}),
    ),
    NotificationEventType.BRIEF_REVISION_REQUESTED.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.BRIEF_REVISION_REQUESTED.value,
        group=EVENT_GROUP_DELIVERY,
        label="Revizyon istendi",
        portals=frozenset({_AGENCY}),
    ),
    NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value,
        group=EVENT_GROUP_DELIVERY,
        label="Teslimat revizyonu istendi",
        portals=frozenset({_AGENCY}),
    ),
    NotificationEventType.INVOICE_SENT.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.INVOICE_SENT.value,
        group=EVENT_GROUP_FINANCE,
        label="Fatura gönderildi",
        portals=frozenset({_BRAND}),
    ),
    NotificationEventType.INVOICE_DUE_SOON.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.INVOICE_DUE_SOON.value,
        group=EVENT_GROUP_FINANCE,
        label="Fatura vadesi yaklaşıyor",
        portals=frozenset({_BRAND}),
    ),
    NotificationEventType.INVOICE_OVERDUE.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.INVOICE_OVERDUE.value,
        group=EVENT_GROUP_FINANCE,
        label="Fatura vadesi geçti",
        portals=frozenset({_AGENCY}),
        required_permission=Permission.INVOICE_APPROVE,
    ),
    NotificationEventType.INVOICE_PAYMENT_RECEIVED.value: WhatsAppEventUIMeta(
        event_type=NotificationEventType.INVOICE_PAYMENT_RECEIVED.value,
        group=EVENT_GROUP_FINANCE,
        label="Ödeme alındı",
        portals=frozenset({_AGENCY}),
        required_permission=Permission.INVOICE_VIEW,
    ),
}

# Every catalog event must have UI metadata — asserted at import time so a
# future catalog addition can't silently ship without a group/label/portal.
_missing = set(WHATSAPP_EVENT_CATALOG) - set(WHATSAPP_EVENT_UI_CATALOG)
if _missing:  # pragma: no cover - defensive, guards future drift
    raise RuntimeError(f"WhatsApp events missing UI metadata: {sorted(_missing)}")


@dataclass(frozen=True)
class UserRoleContext:
    user_type: str
    role: str | None
    permissions: frozenset[Permission]

    @property
    def portal(self) -> str | None:
        if self.user_type == UserType.AGENCY_USER.value:
            return _AGENCY
        if self.user_type == UserType.BRAND_USER.value:
            return _BRAND
        return None


async def resolve_role_context(db: AsyncSession, user: User) -> UserRoleContext:
    """Resolve the caller's tenant role once, for both permission checks and
    the event-visibility filter below. Fail-closed: no active membership
    found → no permissions, no visible events."""
    if user.is_platform_admin:
        return UserRoleContext(
            user_type=UserType.PLATFORM_ADMIN.value, role=None, permissions=frozenset()
        )

    if user.user_type == UserType.AGENCY_USER.value:
        role = await db.scalar(
            select(AgencyMember.role).where(
                AgencyMember.user_id == user.id,
                AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
                AgencyMember.deleted_at.is_(None),
            )
        )
        perms = get_permissions_for_agency_role(role) if role else frozenset()
        return UserRoleContext(user_type=user.user_type, role=role, permissions=perms)

    if user.user_type == UserType.BRAND_USER.value:
        role = await db.scalar(
            select(BrandMember.role).where(
                BrandMember.user_id == user.id,
                BrandMember.status == BrandMemberStatus.ACTIVE.value,
                BrandMember.deleted_at.is_(None),
            )
        )
        perms = get_permissions_for_brand_role(role) if role else frozenset()
        return UserRoleContext(user_type=user.user_type, role=role, permissions=perms)

    return UserRoleContext(user_type=user.user_type, role=None, permissions=frozenset())


def is_event_visible_for_role(event_type: str, role_ctx: UserRoleContext) -> bool:
    """True if this role should see (and be allowed to toggle) this event's
    WhatsApp control at all — the same check gates both the list endpoint
    and the update endpoint, so a hidden toggle can never be written via a
    direct API call either."""
    meta = WHATSAPP_EVENT_UI_CATALOG.get(event_type)
    if meta is None:
        return False
    if role_ctx.portal is None or role_ctx.portal not in meta.portals:
        return False
    return meta.required_permission is None or meta.required_permission in role_ctx.permissions


def list_visible_events_for_role(role_ctx: UserRoleContext) -> list[WhatsAppEventUIMeta]:
    return [
        meta
        for meta in WHATSAPP_EVENT_UI_CATALOG.values()
        if is_event_visible_for_role(meta.event_type, role_ctx)
    ]


CONSENT_SOURCE_IN_APP_TOGGLE = "in_app_toggle"
CONSENT_VERSION_CURRENT = "2026-07-28"


async def set_whatsapp_consent(
    db: AsyncSession,
    *,
    user: User,
    opt_in: bool,
) -> User:
    """The sole authority for the WhatsApp master toggle + consent record.

    A user may only ever consent for themselves — every call site passes the
    *authenticated* user as both actor and subject, never an id supplied in
    a request body, so there is no code path for an Owner/Admin to opt in or
    out on someone else's behalf.
    """
    from datetime import UTC, datetime

    from app.repositories.notification import NotificationPreferenceRepository

    now = datetime.now(UTC)
    if opt_in:
        user.whatsapp_opt_in = True
        user.whatsapp_opt_in_at = now
        user.whatsapp_opt_out_at = None
        user.whatsapp_consent_source = CONSENT_SOURCE_IN_APP_TOGGLE
        user.whatsapp_consent_version = CONSENT_VERSION_CURRENT
    else:
        user.whatsapp_opt_in = False
        user.whatsapp_opt_out_at = now

    db.add(user)

    pref_repo = NotificationPreferenceRepository(db)
    pref = await pref_repo.get_or_create(user.id)
    await pref_repo.update(
        pref,
        email_enabled=pref.email_enabled,
        whatsapp_enabled=opt_in,
        in_app_enabled=pref.in_app_enabled,
    )

    await db.flush()
    await db.refresh(user)
    return user

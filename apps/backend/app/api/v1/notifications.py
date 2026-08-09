from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_current_user, require_permission
from app.core.config import settings
from app.core.rbac import Permission
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.repositories.notification import (
    NotificationDeliveryRepository,
    NotificationEventRepository,
    NotificationPreferenceRepository,
    NotificationRepository,
)
from app.repositories.whatsapp_template import WhatsAppTemplateRepository
from app.schemas.notification import (
    NotificationListResponse,
    NotificationPreferenceRead,
    NotificationPreferenceStatusRead,
    NotificationPreferenceUpdate,
    NotificationRead,
    NotificationRealtimeTicketRead,
    PhoneStatusRead,
    WhatsAppAgencySummaryRead,
    WhatsAppConsentRead,
    WhatsAppConsentUpdate,
    WhatsAppDeliveryHistoryItemRead,
    WhatsAppDeliveryHistoryPage,
    WhatsAppEventPreferenceRead,
    WhatsAppEventPreferenceUpdate,
    WhatsAppTemplateMatrixRowRead,
    WhatsAppTemplatePreviewRead,
    WhatsAppUserStatusRead,
)
from app.schemas.whatsapp_test_send import WhatsAppTestSendResponse
from app.services.notification_realtime import (
    NotificationConnectionClaims,
    RealtimeUnavailableError,
    consume_ticket,
    is_allowed_websocket_origin,
    issue_ticket,
    notification_connection_hub,
    queue_notification_signal,
)
from app.services.notification_routes import build_notification_action_url
from app.services.phone_utils import mask_phone_e164
from app.services.whatsapp_event_catalog import get_event_definition
from app.services.whatsapp_preference_service import WHATSAPP_EVENT_UI_CATALOG, UserRoleContext

notification_router = APIRouter(prefix="/notifications", tags=["notifications"])

_WS_VIEW = Depends(require_permission(Permission.AGENCY_VIEW))
_WS_MANAGE_NOTIFICATIONS = Depends(require_permission(Permission.AGENCY_MANAGE_NOTIFICATIONS))
_PORTAL = "agency"


async def _to_reads(items: list[Notification], db: AsyncSession) -> list[NotificationRead]:
    """Attach a safe, precomputed action_url to each notification (batched)."""
    event_repo = NotificationEventRepository(db)
    event_ids = [n.event_id for n in items if n.event_id is not None]
    events_by_id = await event_repo.get_by_ids(event_ids)
    reads: list[NotificationRead] = []
    for n in items:
        event = events_by_id.get(n.event_id) if n.event_id else None
        action_url = (
            build_notification_action_url(event.event_type, event.payload, _PORTAL)
            if event is not None
            else None
        )
        base = NotificationRead.model_validate(n)
        reads.append(base.model_copy(update={"action_url": action_url}))
    return reads


async def _to_read(notif: Notification, db: AsyncSession) -> NotificationRead:
    reads = await _to_reads([notif], db)
    return reads[0]


@notification_router.get("", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: Annotated[bool, Query()] = False,
    include_archived: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    workspace: WorkspaceContext = _WS_VIEW,
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    repo = NotificationRepository(db)
    items = await repo.list_for_user(
        user_id=workspace.user.id,
        agency_id=workspace.agency.id,
        unread_only=unread_only,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    unread_count = await repo.count_unread(
        user_id=workspace.user.id,
        agency_id=workspace.agency.id,
    )
    return NotificationListResponse(
        items=await _to_reads(items, db),
        unread_count=unread_count,
    )


@notification_router.post(
    "/realtime-ticket",
    response_model=NotificationRealtimeTicketRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_realtime_ticket(
    workspace: WorkspaceContext = _WS_VIEW,
) -> NotificationRealtimeTicketRead:
    try:
        ticket = await issue_ticket(
            NotificationConnectionClaims(
                user_id=str(workspace.user.id),
                portal="agency",
                agency_id=str(workspace.agency.id),
            )
        )
    except RealtimeUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canlı bildirim bağlantısı şu anda kullanılamıyor",
        ) from exc
    return NotificationRealtimeTicketRead(
        ticket=ticket,
        expires_in_seconds=settings.NOTIFICATION_WS_TICKET_TTL_SECONDS,
        websocket_path="/api/v1/notifications/realtime",
    )


@notification_router.websocket("/realtime")
async def notification_realtime_socket(websocket: WebSocket) -> None:
    if not is_allowed_websocket_origin(websocket.headers.get("origin")):
        await websocket.close(code=4403, reason="Origin is not allowed")
        return
    try:
        claims = await consume_ticket(websocket.query_params.get("ticket", ""))
    except RealtimeUnavailableError:
        await websocket.close(code=1013, reason="Real-time service unavailable")
        return
    if claims is None:
        await websocket.close(code=4401, reason="Invalid or expired ticket")
        return

    await notification_connection_hub.connect(websocket, claims)
    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=settings.NOTIFICATION_WS_HEARTBEAT_SECONDS,
                )
                if message.get("type") != "pong":
                    await websocket.send_json({"type": "error", "detail": "Unsupported message"})
            except TimeoutError:
                await websocket.send_json({"type": "ping"})
    except (RuntimeError, WebSocketDisconnect):
        pass
    finally:
        await notification_connection_hub.disconnect(websocket)


@notification_router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: uuid.UUID,
    workspace: WorkspaceContext = _WS_VIEW,
    db: AsyncSession = Depends(get_db),
) -> NotificationRead:
    repo = NotificationRepository(db)
    notif = await repo.get_by_id(notification_id, workspace.user.id)
    if notif is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bildirim bulunamadı")
    await repo.mark_read(notif)
    queue_notification_signal(
        db,
        user_id=workspace.user.id,
        agency_id=workspace.agency.id,
        brand_id=notif.brand_id,
    )
    await db.commit()
    await db.refresh(notif)
    return await _to_read(notif, db)


@notification_router.post("/{notification_id}/archive", response_model=NotificationRead)
async def archive_notification(
    notification_id: uuid.UUID,
    workspace: WorkspaceContext = _WS_VIEW,
    db: AsyncSession = Depends(get_db),
) -> NotificationRead:
    repo = NotificationRepository(db)
    notif = await repo.get_by_id(notification_id, workspace.user.id)
    if notif is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bildirim bulunamadı")
    await repo.archive(notif)
    queue_notification_signal(
        db,
        user_id=workspace.user.id,
        agency_id=workspace.agency.id,
        brand_id=notif.brand_id,
    )
    await db.commit()
    await db.refresh(notif)
    return await _to_read(notif, db)


@notification_router.post("/read-all")
async def mark_all_notifications_read(
    workspace: WorkspaceContext = _WS_VIEW,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    repo = NotificationRepository(db)
    count = await repo.mark_all_read(
        user_id=workspace.user.id,
        agency_id=workspace.agency.id,
    )
    if count:
        queue_notification_signal(
            db,
            user_id=workspace.user.id,
            agency_id=workspace.agency.id,
            brand_id=None,
        )
    await db.commit()
    return {"marked_read": count}


async def _build_pref_status(
    pref: object,
    user: User,
    db: AsyncSession,
) -> NotificationPreferenceStatusRead:
    """Enrich a preference ORM row with live provider/user context."""
    from app.services.whatsapp_provider import DisabledWhatsAppProvider, WhatsAppProviderFactory

    try:
        provider = await WhatsAppProviderFactory.get_provider(db)
        wa_active = (
            not isinstance(provider, DisabledWhatsAppProvider) and provider.validate_config()
        )
    except Exception:
        wa_active = False

    base = NotificationPreferenceRead.model_validate(pref)
    return NotificationPreferenceStatusRead(
        **base.model_dump(),
        whatsapp_provider_active=wa_active,
        has_phone_number=bool(user.phone_number),
        whatsapp_opt_in=user.whatsapp_opt_in,
    )


@notification_router.get("/preferences", response_model=NotificationPreferenceStatusRead)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferenceStatusRead:
    repo = NotificationPreferenceRepository(db)
    pref = await repo.get_or_create(current_user.id)
    await db.commit()
    await db.refresh(pref)
    return await _build_pref_status(pref, current_user, db)


@notification_router.patch("/preferences", response_model=NotificationPreferenceStatusRead)
async def update_preferences(
    payload: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferenceStatusRead:
    repo = NotificationPreferenceRepository(db)
    pref = await repo.get_or_create(current_user.id)
    updated = await repo.update(
        pref,
        email_enabled=payload.email_enabled,
        whatsapp_enabled=payload.whatsapp_enabled,
        in_app_enabled=payload.in_app_enabled,
    )
    await db.commit()
    await db.refresh(updated)
    return await _build_pref_status(updated, current_user, db)


@notification_router.post("/whatsapp/test", response_model=WhatsAppTestSendResponse)
async def send_whatsapp_test_notification(
    workspace: WorkspaceContext = _WS_VIEW,
    db: AsyncSession = Depends(get_db),
) -> WhatsAppTestSendResponse:
    """Self-service controlled WhatsApp test send — any active agency member
    (not just Owner/Admin, widened in Part 6B-2 so every user's own settings
    page can offer this) may trigger this for their own opted-in number.

    Takes no request body — the recipient is never caller-supplied (see
    app.services.whatsapp_test_send_service for the full gating chain:
    demo-tenant, consent, phone resolution, rate limit, approved-template).
    """
    from app.services.whatsapp_test_send_service import send_test_message

    outcome = await send_test_message(db, agency=workspace.agency, user=workspace.user)
    return WhatsAppTestSendResponse(
        delivery_id=outcome.delivery_id,
        masked_recipient=outcome.masked_recipient,
        status=outcome.status,
        provider=outcome.provider,
        template_key=outcome.template_key,
        provider_message_id=outcome.provider_message_id,
        safe_error=outcome.safe_error,
    )


# ── WhatsApp preferences (Part 6B-2) — self-service, any authenticated user ──


async def _resolve_demo_tenant(db: AsyncSession, role_ctx: UserRoleContext, user: User) -> bool:
    """Best-effort demo-tenant flag for the current user's own tenant —
    used only to explain suppressed real sends, never to gate anything
    security-sensitive (that gating already happens server-side per-send)."""
    from sqlalchemy import select as _select

    from app.models.agency import Agency
    from app.models.agency_member import AgencyMember
    from app.models.brand import Brand
    from app.models.brand_member import BrandMember
    from app.models.enums import AgencyMemberStatus, BrandMemberStatus

    if role_ctx.portal == "agency":
        stmt = (
            _select(Agency.is_demo)
            .join(AgencyMember, AgencyMember.agency_id == Agency.id)
            .where(
                AgencyMember.user_id == user.id,
                AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
                AgencyMember.deleted_at.is_(None),
            )
            .limit(1)
        )
        return bool(await db.scalar(stmt))
    if role_ctx.portal == "brand":
        stmt = (
            _select(Agency.is_demo)
            .join(Brand, Brand.agency_id == Agency.id)
            .join(BrandMember, BrandMember.brand_id == Brand.id)
            .where(
                BrandMember.user_id == user.id,
                BrandMember.status == BrandMemberStatus.ACTIVE.value,
                BrandMember.deleted_at.is_(None),
            )
            .limit(1)
        )
        return bool(await db.scalar(stmt))
    return False


async def _build_whatsapp_user_status(
    current_user: User, db: AsyncSession
) -> WhatsAppUserStatusRead:
    from app.repositories.notification import (
        NotificationEventPreferenceRepository,
        NotificationPreferenceRepository,
    )
    from app.services.whatsapp_preference_service import (
        EVENT_GROUP_LABELS,
        list_visible_events_for_role,
        resolve_role_context,
    )
    from app.services.whatsapp_provider import DisabledWhatsAppProvider, WhatsAppProviderFactory

    pref_repo = NotificationPreferenceRepository(db)
    event_pref_repo = NotificationEventPreferenceRepository(db)
    delivery_repo = NotificationDeliveryRepository(db)

    pref = await pref_repo.get_or_create(current_user.id)
    role_ctx = await resolve_role_context(db, current_user)
    custom_events = await event_pref_repo.list_for_user(current_user.id)

    try:
        provider = await WhatsAppProviderFactory.get_provider(db)
        wa_active = (
            not isinstance(provider, DisabledWhatsAppProvider) and provider.validate_config()
        )
    except Exception:
        wa_active = False

    template_repo = WhatsAppTemplateRepository(db)
    events: list[WhatsAppEventPreferenceRead] = []
    for meta in list_visible_events_for_role(role_ctx):
        defn = get_event_definition(meta.event_type)
        custom_row = custom_events.get(meta.event_type)
        template = (
            await template_repo.get_approved(
                defn.template_key, locale=defn.locale_fallback, provider="twilio"
            )
            if defn
            else None
        )
        events.append(
            WhatsAppEventPreferenceRead(
                event_type=meta.event_type,
                event_label=meta.label,
                group=meta.group,
                group_label=EVENT_GROUP_LABELS[meta.group],
                whatsapp_enabled=custom_row.whatsapp_enabled if custom_row else True,
                template_ready=template is not None,
                is_customized=custom_row is not None,
                updated_at=custom_row.updated_at if custom_row else None,
            )
        )

    is_demo = await _resolve_demo_tenant(db, role_ctx, current_user)

    last_delivery = await delivery_repo.latest_for_user(current_user.id)

    return WhatsAppUserStatusRead(
        whatsapp_provider_active=wa_active,
        phone=PhoneStatusRead(
            has_phone_number=bool(current_user.phone_number),
            phone_masked=(
                mask_phone_e164(current_user.phone_number) if current_user.phone_number else None
            ),
            phone_verified=current_user.phone_verified_at is not None,
        ),
        consent=WhatsAppConsentRead(
            whatsapp_opt_in=current_user.whatsapp_opt_in,
            whatsapp_opt_in_at=current_user.whatsapp_opt_in_at,
            whatsapp_opt_out_at=current_user.whatsapp_opt_out_at,
            whatsapp_consent_source=current_user.whatsapp_consent_source,
            whatsapp_consent_version=current_user.whatsapp_consent_version,
        ),
        master_enabled=pref.whatsapp_enabled,
        is_demo_tenant=is_demo,
        events=events,
        last_delivery_status=last_delivery.status if last_delivery else None,
        last_delivery_at=last_delivery.created_at if last_delivery else None,
        last_safe_error=(
            last_delivery.error_message if last_delivery and last_delivery.error_message else None
        ),
    )


@notification_router.get("/whatsapp/status", response_model=WhatsAppUserStatusRead)
async def get_whatsapp_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WhatsAppUserStatusRead:
    """Full WhatsApp status for the current user's own settings page —
    phone/consent state, master toggle, role-filtered event toggles, and the
    most recent delivery outcome. Self-scoped only; no id in the path."""
    return await _build_whatsapp_user_status(current_user, db)


@notification_router.post("/whatsapp/consent", response_model=WhatsAppUserStatusRead)
async def update_whatsapp_consent(
    payload: WhatsAppConsentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WhatsAppUserStatusRead:
    """The sole endpoint that may flip the WhatsApp master toggle — always
    acts on the authenticated caller, never on an id from the request body,
    so an Owner/Admin cannot open consent on another user's behalf."""
    from app.services.whatsapp_preference_service import set_whatsapp_consent

    await set_whatsapp_consent(db, user=current_user, opt_in=payload.opt_in)
    await db.commit()
    await db.refresh(current_user)
    return await _build_whatsapp_user_status(current_user, db)


@notification_router.patch(
    "/whatsapp/event-preferences/{event_type}", response_model=WhatsAppEventPreferenceRead
)
async def update_whatsapp_event_preference(
    event_type: str,
    payload: WhatsAppEventPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WhatsAppEventPreferenceRead:
    from app.repositories.notification import NotificationEventPreferenceRepository
    from app.services.whatsapp_preference_service import (
        EVENT_GROUP_LABELS,
        is_event_visible_for_role,
        resolve_role_context,
    )

    role_ctx = await resolve_role_context(db, current_user)
    if not is_event_visible_for_role(event_type, role_ctx):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu event için WhatsApp tercihi değiştirme yetkiniz yok",
        )

    event_pref_repo = NotificationEventPreferenceRepository(db)
    row = await event_pref_repo.upsert_whatsapp_toggle(
        current_user.id,
        event_type,
        payload.whatsapp_enabled,
        updated_by_user_id=current_user.id,
    )
    await db.commit()

    defn = get_event_definition(event_type)
    template_repo = WhatsAppTemplateRepository(db)
    template = (
        await template_repo.get_approved(
            defn.template_key, locale=defn.locale_fallback, provider="twilio"
        )
        if defn
        else None
    )
    meta = WHATSAPP_EVENT_UI_CATALOG[event_type]
    return WhatsAppEventPreferenceRead(
        event_type=event_type,
        event_label=meta.label,
        group=meta.group,
        group_label=EVENT_GROUP_LABELS[meta.group],
        whatsapp_enabled=row.whatsapp_enabled,
        template_ready=template is not None,
        is_customized=True,
        updated_at=row.updated_at,
    )


# ── WhatsApp Owner/Admin management center (Part 6B-2) ──────────────────────
# All four endpoints below require AGENCY_MANAGE_NOTIFICATIONS (Owner/Admin
# only) and are hard-scoped to workspace.agency.id — no cross-tenant leakage,
# no secrets, no raw phone numbers, no content_sid values.


@notification_router.get("/whatsapp/summary", response_model=WhatsAppAgencySummaryRead)
async def get_whatsapp_agency_summary(
    workspace: WorkspaceContext = _WS_MANAGE_NOTIFICATIONS,
    db: AsyncSession = Depends(get_db),
) -> WhatsAppAgencySummaryRead:
    from app.services.whatsapp_admin_service import build_agency_summary

    summary = await build_agency_summary(
        db, agency_id=workspace.agency.id, is_demo=workspace.agency.is_demo
    )
    return WhatsAppAgencySummaryRead(
        connection_status=summary.connection_status,
        sender_masked=summary.sender_masked,
        environment=summary.environment,
        opted_in_users=summary.opted_in_users,
        whatsapp_enabled_users=summary.whatsapp_enabled_users,
        templates_ready=summary.templates_ready,
        templates_not_ready=summary.templates_not_ready,
        deliveries_24h=summary.deliveries_24h,
        deliveries_7d=summary.deliveries_7d,
        last_safe_error=summary.last_safe_error,
        demo_tenant=summary.demo_tenant,
        retry_queue=summary.retry_queue,
        retry_exhausted=summary.retry_exhausted,
        delivery_success_rate_7d=summary.delivery_success_rate_7d,
        read_rate_7d=summary.read_rate_7d,
        top_failure_category_7d=summary.top_failure_category_7d,
    )


@notification_router.get(
    "/whatsapp/template-matrix", response_model=list[WhatsAppTemplateMatrixRowRead]
)
async def get_whatsapp_template_matrix(
    workspace: WorkspaceContext = _WS_MANAGE_NOTIFICATIONS,
    db: AsyncSession = Depends(get_db),
) -> list[WhatsAppTemplateMatrixRowRead]:
    from app.services.whatsapp_admin_service import build_template_matrix

    rows = await build_template_matrix(db)
    return [
        WhatsAppTemplateMatrixRowRead(
            event_type=r.event_type,
            event_label=r.event_label,
            template_key=r.template_key,
            locale=r.locale,
            status=r.status,
            enabled=r.enabled,
            has_content_sid=r.has_content_sid,
            approved_at=r.approved_at,
            recipient_policy=r.recipient_policy,
        )
        for r in rows
    ]


@notification_router.get(
    "/whatsapp/template-preview/{event_type}", response_model=WhatsAppTemplatePreviewRead
)
async def get_whatsapp_template_preview(
    event_type: str,
    workspace: WorkspaceContext = _WS_MANAGE_NOTIFICATIONS,
) -> WhatsAppTemplatePreviewRead:
    from app.services.whatsapp_admin_service import build_template_preview

    preview = build_template_preview(event_type)
    if preview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event bulunamadı")
    return WhatsAppTemplatePreviewRead(
        event_type=preview.event_type,
        event_label=preview.event_label,
        template_key=preview.template_key,
        locale=preview.locale,
        status=preview.status,
        sample_message=preview.sample_message,
        variable_names=preview.variable_names,
        recipient_roles=preview.recipient_roles,
        sensitive_data_note=preview.sensitive_data_note,
    )


@notification_router.get("/whatsapp/deliveries", response_model=WhatsAppDeliveryHistoryPage)
async def list_whatsapp_deliveries(
    event_type: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    template_key: Annotated[str | None, Query()] = None,
    user_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    workspace: WorkspaceContext = _WS_MANAGE_NOTIFICATIONS,
    db: AsyncSession = Depends(get_db),
) -> WhatsAppDeliveryHistoryPage:
    delivery_repo = NotificationDeliveryRepository(db)
    rows, total = await delivery_repo.list_for_agency(
        workspace.agency.id,
        event_type=event_type,
        status_filter=status_filter,
        template_key=template_key,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    recipient_ids = [r.recipient_user_id for r in rows if r.recipient_user_id is not None]
    names_by_id: dict[uuid.UUID, str] = {}
    if recipient_ids:
        from sqlalchemy import select as _select

        result = await db.execute(
            _select(User.id, User.full_name).where(User.id.in_(recipient_ids))
        )
        names_by_id = {row[0]: row[1] for row in result.all()}

    event_repo = NotificationEventRepository(db)
    events_by_id = await event_repo.get_by_ids([r.event_id for r in rows])

    items = [
        WhatsAppDeliveryHistoryItemRead(
            id=r.id,
            created_at=r.created_at,
            event_type=(events_by_id[r.event_id].event_type if r.event_id in events_by_id else ""),
            template_key=r.template_key,
            recipient_phone_masked=r.recipient_phone_masked,
            recipient_display_name=(
                names_by_id.get(r.recipient_user_id) if r.recipient_user_id else None
            ),
            provider=r.provider,
            status=r.status,
            attempt_count=r.attempt_count,
            safe_error=r.error_message,
            sent_at=r.sent_at,
            delivered_at=r.delivered_at,
            read_at=r.read_at,
        )
        for r in rows
    ]
    return WhatsAppDeliveryHistoryPage(items=items, total=total, limit=limit, offset=offset)

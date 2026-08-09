"""WhatsApp-only recipient narrowing (Part 6B-1).

The domain services already resolve *who gets notified at all* (in-app +
email + WhatsApp share that recipient list — see NotificationDispatcher.
_dispatch). This module only narrows that list further for the WhatsApp
channel specifically, for the two events where the task's role rules are
stricter than what the shared recipient list already encodes:

- BRIEF_SUBMITTED ("approval.requested"): the shared recipient list is "all
  brand members of this brief's brand" (so a brand_viewer sees the in-app/
  email nudge too), but only brand roles holding BRIEF_APPROVE can actually
  act on it — WhatsApp, being an interruptive channel, is reserved for them.
- INVOICE_PAYMENT_RECEIVED: only agency roles holding INVOICE_VIEW may see
  confirmation that a client payment landed.

Every other catalog event returns True unconditionally — no extra DB query,
no behavior change beyond what the domain service already resolved.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import (
    Permission,
    get_permissions_for_agency_role,
    get_permissions_for_brand_role,
)
from app.models.agency_member import AgencyMember
from app.models.brand_member import BrandMember
from app.models.enums import AgencyMemberStatus, BrandMemberStatus, NotificationEventType
from app.models.notification import NotificationEvent
from app.models.user import User

_BRAND_ROLE_GATED_EVENTS: dict[str, Permission] = {
    NotificationEventType.BRIEF_SUBMITTED.value: Permission.BRIEF_APPROVE,
}
_AGENCY_ROLE_GATED_EVENTS: dict[str, Permission] = {
    NotificationEventType.INVOICE_PAYMENT_RECEIVED.value: Permission.INVOICE_VIEW,
}


async def is_whatsapp_role_eligible(
    db: AsyncSession, event: NotificationEvent, recipient: User
) -> bool:
    """True if `recipient` may receive this event over WhatsApp specifically.

    Fail-closed: if a gated event has no resolvable membership row (e.g. the
    recipient somehow isn't an active member of the event's brand/agency),
    this returns False rather than defaulting to "send"."""
    brand_permission = _BRAND_ROLE_GATED_EVENTS.get(event.event_type)
    if brand_permission is not None:
        if event.brand_id is None:
            return False
        role = await db.scalar(
            select(BrandMember.role).where(
                BrandMember.brand_id == event.brand_id,
                BrandMember.user_id == recipient.id,
                BrandMember.status == BrandMemberStatus.ACTIVE.value,
                BrandMember.deleted_at.is_(None),
            )
        )
        if role is None:
            return False
        return brand_permission in get_permissions_for_brand_role(role)

    agency_permission = _AGENCY_ROLE_GATED_EVENTS.get(event.event_type)
    if agency_permission is not None:
        if event.agency_id is None:
            return False
        role = await db.scalar(
            select(AgencyMember.role).where(
                AgencyMember.agency_id == event.agency_id,
                AgencyMember.user_id == recipient.id,
                AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
                AgencyMember.deleted_at.is_(None),
            )
        )
        if role is None:
            return False
        return agency_permission in get_permissions_for_agency_role(role)

    return True


__all__ = ["is_whatsapp_role_eligible"]

"""E2E fixture for apps/frontend/e2e/whatsapp-event-delivery-flow.spec.ts (Part 6B-3).

Seeds one agency (owner opted-in, approved `brief_created` template) with a
representative spread of WhatsApp delivery lifecycle rows — sent, delivered,
read, a retryable failure sitting in the retry queue, a retry-exhausted
failure, a cancelled (opt-out) row, and a skipped_demo_tenant row for a
separate demo agency — plus a second, unrelated agency for the
cross-tenant-isolation assertion. No real Twilio call is ever made; delivery
rows are inserted directly at their final lifecycle status, the same way the
existing whatsapp-preferences-flow fixture asserts UI state without a live
provider.

Two modes:
  python e2e_seed_whatsapp_delivery_flow.py seed     -> prints E2E_* env vars
  python e2e_seed_whatsapp_delivery_flow.py cleanup  -> deletes the fixture

Safety: refuses to run unless DATABASE_URL resolves to a local host and
APP_ENV is not "production".
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.agency import Agency  # noqa: E402
from app.models.agency_member import AgencyMember  # noqa: E402
from app.models.enums import (  # noqa: E402
    AgencyMemberRole,
    AgencyMemberStatus,
    NotificationChannel,
    NotificationDeliveryStatus,
    UserType,
    WhatsAppTemplateStatus,
)
from app.models.notification import (  # noqa: E402
    NotificationDelivery,
    NotificationEvent,
    NotificationPreference,
)
from app.models.user import User  # noqa: E402
from app.repositories.notification import NotificationPreferenceRepository  # noqa: E402
from app.repositories.whatsapp_template import WhatsAppTemplateRepository  # noqa: E402

OWNER_EMAIL = "flobrief-e2e-wadelivery-owner@example.com"
OTHER_OWNER_EMAIL = "flobrief-e2e-wadelivery-other-owner@example.com"
DEMO_OWNER_EMAIL = "flobrief-e2e-wadelivery-demo-owner@example.com"
PASSWORD = "E2eTest1234!"
READY_TEMPLATE_CODE = "brief_created"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_ALL_EMAILS = (OWNER_EMAIL, OTHER_OWNER_EMAIL, DEMO_OWNER_EMAIL)


def _assert_local_test_database() -> None:
    host = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing to run: DATABASE_URL host {host!r} is not a local host {_LOCAL_HOSTS}."
        )
    if settings.is_production:
        raise RuntimeError("Refusing to run: APP_ENV=production.")


async def _delete_fixture(session) -> None:
    for email in _ALL_EMAILS:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            continue
        agencies = (
            (
                await session.execute(
                    select(Agency)
                    .join(AgencyMember, AgencyMember.agency_id == Agency.id)
                    .where(AgencyMember.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        for agency in agencies:
            await session.delete(agency)
        await session.flush()
        await session.delete(user)
    await session.commit()

    repo = WhatsAppTemplateRepository(session)
    tpl = await repo.get_by_code(READY_TEMPLATE_CODE)
    if tpl is not None:
        tpl.status = WhatsAppTemplateStatus.DRAFT.value
        tpl.content_sid = None
        session.add(tpl)
        await session.commit()


async def cleanup() -> None:
    _assert_local_test_database()
    async with AsyncSessionLocal() as session:
        await _delete_fixture(session)
    print("Cleanup complete.")


async def _seed_delivery(
    session,
    *,
    agency_id: uuid.UUID,
    recipient_id: uuid.UUID,
    status: str,
    template_key: str | None = READY_TEMPLATE_CODE,
    error_message: str | None = None,
    failure_category: str | None = None,
    next_retry_at: datetime | None = None,
    retry_exhausted_at: datetime | None = None,
    cancelled_at: datetime | None = None,
) -> None:
    event = NotificationEvent(
        event_type="brief.created",
        payload={"brief_id": str(uuid.uuid4()), "brief_title": "E2E Delivery Flow Brief"},
        agency_id=agency_id,
    )
    session.add(event)
    await session.flush()
    delivery = NotificationDelivery(
        event_id=event.id,
        channel=NotificationChannel.WHATSAPP.value,
        status=status,
        provider="twilio_production",
        recipient_user_id=recipient_id,
        agency_id=agency_id,
        template_key=template_key,
        recipient_phone_masked="+905***01" if template_key else None,
        error_message=error_message,
        failure_category=failure_category,
        next_retry_at=next_retry_at,
        retry_exhausted_at=retry_exhausted_at,
        cancelled_at=cancelled_at,
        attempt_count=1 if status != NotificationDeliveryStatus.SKIPPED_DEMO_TENANT.value else 0,
        idempotency_key=f"e2e-delivery-{uuid.uuid4().hex}",
    )
    session.add(delivery)


async def seed() -> None:
    _assert_local_test_database()
    async with AsyncSessionLocal() as session:
        await _delete_fixture(session)

        pw_hash = hash_password(PASSWORD)
        agency = Agency(name="E2E WA Delivery Agency", slug="e2e-wadelivery-agency", is_demo=False)
        other_agency = Agency(
            name="E2E WA Delivery Other Agency", slug="e2e-wadelivery-other-agency", is_demo=False
        )
        now = datetime.now(UTC)
        demo_agency = Agency(
            name="E2E WA Delivery Demo Agency",
            slug="e2e-wadelivery-demo-agency",
            is_demo=True,
            demo_started_at=now,
            demo_expires_at=now + timedelta(days=7),
        )

        owner = User(
            email=OWNER_EMAIL,
            password_hash=pw_hash,
            full_name="E2E WA Delivery Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
            phone_number="+905551230101",
            whatsapp_opt_in=True,
            whatsapp_opt_in_at=now,
        )
        other_owner = User(
            email=OTHER_OWNER_EMAIL,
            password_hash=pw_hash,
            full_name="E2E WA Delivery Other Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
            phone_number="+905551230102",
        )
        demo_owner = User(
            email=DEMO_OWNER_EMAIL,
            password_hash=pw_hash,
            full_name="E2E WA Delivery Demo Owner",
            user_type=UserType.AGENCY_USER.value,
            is_active=True,
            is_verified=True,
            phone_number="+905551230103",
            whatsapp_opt_in=True,
            whatsapp_opt_in_at=now,
        )

        session.add_all([agency, other_agency, demo_agency, owner, other_owner, demo_owner])
        await session.flush()

        session.add_all(
            [
                AgencyMember(
                    agency_id=agency.id,
                    user_id=owner.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    agency_id=other_agency.id,
                    user_id=other_owner.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                AgencyMember(
                    agency_id=demo_agency.id,
                    user_id=demo_owner.id,
                    role=AgencyMemberRole.OWNER.value,
                    status=AgencyMemberStatus.ACTIVE.value,
                ),
                NotificationPreference(user_id=owner.id, whatsapp_enabled=True),
                NotificationPreference(user_id=demo_owner.id, whatsapp_enabled=True),
            ]
        )
        await session.commit()

        pref_repo = NotificationPreferenceRepository(session)
        pref = await pref_repo.get_or_create(owner.id)
        await pref_repo.update(pref, email_enabled=True, whatsapp_enabled=True, in_app_enabled=True)

        template_repo = WhatsAppTemplateRepository(session)
        tpl = await template_repo.get_by_code(READY_TEMPLATE_CODE)
        assert tpl is not None, "migration seed must have created whatsapp_templates.brief_created"
        tpl.status = WhatsAppTemplateStatus.APPROVED.value
        tpl.content_sid = "HXe2edeliveryfake"
        session.add(tpl)
        await session.commit()

        # A representative spread of lifecycle outcomes for owner's agency.
        await _seed_delivery(
            session,
            agency_id=agency.id,
            recipient_id=owner.id,
            status=NotificationDeliveryStatus.SENT.value,
        )
        await _seed_delivery(
            session,
            agency_id=agency.id,
            recipient_id=owner.id,
            status=NotificationDeliveryStatus.DELIVERED.value,
        )
        await _seed_delivery(
            session,
            agency_id=agency.id,
            recipient_id=owner.id,
            status=NotificationDeliveryStatus.READ.value,
        )
        await _seed_delivery(
            session,
            agency_id=agency.id,
            recipient_id=owner.id,
            status=NotificationDeliveryStatus.FAILED.value,
            error_message="Simulated transient failure",
            failure_category="timeout",
            next_retry_at=now + timedelta(minutes=10),
        )
        await _seed_delivery(
            session,
            agency_id=agency.id,
            recipient_id=owner.id,
            status=NotificationDeliveryStatus.FAILED.value,
            error_message="Simulated permanent failure",
            failure_category="invalid_recipient",
            retry_exhausted_at=now,
        )
        await _seed_delivery(
            session,
            agency_id=agency.id,
            recipient_id=owner.id,
            status=NotificationDeliveryStatus.CANCELLED.value,
            error_message="WhatsApp STOP opt-out",
            cancelled_at=now,
        )
        await _seed_delivery(
            session,
            agency_id=demo_agency.id,
            recipient_id=demo_owner.id,
            status=NotificationDeliveryStatus.SKIPPED_DEMO_TENANT.value,
            error_message="Demo tenant'ta WhatsApp bildirimi gönderilmez.",
            template_key=None,
        )
        await session.commit()

        print(f"E2E_OWNER_EMAIL={OWNER_EMAIL}")
        print(f"E2E_OTHER_OWNER_EMAIL={OTHER_OWNER_EMAIL}")
        print(f"E2E_DEMO_OWNER_EMAIL={DEMO_OWNER_EMAIL}")
        print(f"E2E_PASSWORD={PASSWORD}")
        print(f"E2E_AGENCY_ID={agency.id}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if mode == "cleanup":
        asyncio.run(cleanup())
    else:
        asyncio.run(seed())


if __name__ == "__main__":
    main()

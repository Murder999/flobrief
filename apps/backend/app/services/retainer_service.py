"""RetainerService: computes the current retainer period for a brand whose
active `CommercialTerms.billing_model == "retainer"`, with timezone-safe
period boundaries and included/used/remaining/overage minute math.

Deviation from plan §7 (documented, justified — checked before writing):
`CommercialTerms` (Phase 3, `app/models/commercial_terms.py`) has **no**
`retainer_period` field. Per the task's explicit fallback instruction, period
cadence is derived as a fixed **monthly** cadence anchored to
`CommercialTerms.valid_from`, computed in the brand's timezone
(`Brand.timezone`, falling back to `Europe/Istanbul` — mirrors
`TimeOffService`'s existing default). This is the "documented v1
simplification" the plan explicitly allows for when the field doesn't exist.

Timezone-safety: period boundaries are computed as local-midnight-to-local-
midnight in the brand's IANA timezone, then converted to UTC instants with an
**exclusive** end boundary — the same technique `TimeOffService.
compute_all_day_utc_bounds` uses for all-day leave, so a late-night entry
near a month boundary is never miscounted into the wrong period, and a
`TimeEntry` can never count toward two periods (adjacent periods are
contiguous, never overlapping).
"""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.rbac import Permission, get_permissions_for_agency_role
from app.models.commercial_terms import CommercialTerms
from app.models.enums import AgencyMemberStatus, CommercialTermsBillingModel, NotificationEventType
from app.models.notification import NotificationEvent
from app.repositories.agency_member import AgencyMemberRepository
from app.repositories.agency_settings import AgencySettingsRepository
from app.repositories.brand import BrandRepository
from app.repositories.commercial_terms import CommercialTermsRepository
from app.repositories.time_entry import TimeEntryRepository
from app.services.notification_dispatcher import NotificationDispatcher

_DEFAULT_TIMEZONE = "Europe/Istanbul"


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@dataclass(frozen=True)
class RetainerPeriod:
    period_start: date
    period_end: date  # inclusive, local calendar date
    period_start_utc: datetime
    period_end_utc: datetime  # exclusive UTC instant


def compute_current_period(
    anchor: date, timezone: str, as_of: date | None = None
) -> RetainerPeriod:
    """Pure function, unit-testable independent of the DB — the monthly
    period containing `as_of` (default: today in `timezone`), anchored to
    `anchor`'s calendar day-of-month."""
    tz = ZoneInfo(timezone)
    ref = as_of if as_of is not None else datetime.now(tz).date()

    months_elapsed = (ref.year - anchor.year) * 12 + (ref.month - anchor.month)
    period_start = _add_months(anchor, months_elapsed)
    if period_start > ref:
        months_elapsed -= 1
        period_start = _add_months(anchor, months_elapsed)
    next_period_start = _add_months(anchor, months_elapsed + 1)

    start_utc = datetime.combine(period_start, time.min, tzinfo=tz).astimezone(UTC)
    end_utc = datetime.combine(next_period_start, time.min, tzinfo=tz).astimezone(UTC)
    return RetainerPeriod(
        period_start=period_start,
        period_end=next_period_start - timedelta(days=1),
        period_start_utc=start_utc,
        period_end_utc=end_utc,
    )


@dataclass(frozen=True)
class RetainerSummary:
    period_start: date
    period_end: date
    included_minutes: int
    rolled_over_minutes: int
    used_minutes: int
    remaining_minutes: int
    overage_minutes: int
    overage_cost_cents: int
    currency: str


class RetainerService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._terms_repo = CommercialTermsRepository(db)
        self._brand_repo = BrandRepository(db)
        self._settings_repo = AgencySettingsRepository(db)
        self._time_entry_repo = TimeEntryRepository(db)
        self._member_repo = AgencyMemberRepository(db)

    async def _billable_minutes_in_period(
        self, agency_id: uuid.UUID, brand_id: uuid.UUID, period: RetainerPeriod
    ) -> int:
        # `list_for_brand`'s `end` filter is inclusive (`started_at <= end`)
        # and offers no exclusive-upper-bound option, so the exclusive period
        # boundary is re-applied here in Python rather than trusted to the
        # repo — this is what guarantees no double-counting at the boundary.
        entries = await self._time_entry_repo.list_for_brand(
            brand_id, agency_id, period.period_start_utc, None
        )
        seconds = sum(
            e.duration_seconds or 0
            for e in entries
            if e.billable
            and e.duration_seconds is not None
            and period.period_start_utc <= e.started_at < period.period_end_utc
        )
        return int(seconds / 60)

    async def _rolled_over_minutes(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID,
        terms: CommercialTerms,
        timezone: str,
        current_period: RetainerPeriod,
    ) -> int:
        """Unused minutes from the immediately preceding period roll forward
        once (non-compounding across multiple skipped periods — a documented
        v1 simplification). Zero if the preceding period predates the terms'
        `valid_from`."""
        prior_ref = current_period.period_start - timedelta(days=1)
        if prior_ref < terms.valid_from:
            return 0
        prior_period = compute_current_period(terms.valid_from, timezone, prior_ref)
        prior_used = await self._billable_minutes_in_period(agency_id, brand_id, prior_period)
        included = terms.retainer_included_minutes or 0
        return max(0, included - prior_used)

    async def get_current_period_summary(
        self, agency_id: uuid.UUID, brand_id: uuid.UUID, as_of: date | None = None
    ) -> RetainerSummary:
        terms = await self._terms_repo.get_active_for_brand(agency_id, brand_id)
        if terms is None or terms.billing_model != CommercialTermsBillingModel.RETAINER.value:
            raise ValidationError("Marka için aktif bir retainer ticari koşulu yok")
        if terms.retainer_included_minutes is None:
            raise ValidationError("Retainer için dahil dakika tanımlanmamış")

        brand = await self._brand_repo.get_by_id_and_agency(brand_id, agency_id)
        if brand is None:
            raise NotFoundError("Marka", str(brand_id))
        timezone = brand.timezone or _DEFAULT_TIMEZONE

        period = compute_current_period(terms.valid_from, timezone, as_of)
        used_minutes = await self._billable_minutes_in_period(agency_id, brand_id, period)

        settings = await self._settings_repo.get_by_agency(agency_id)
        rollover_enabled = settings.retainer_default_rollover if settings is not None else False

        rolled_over_minutes = 0
        if rollover_enabled:
            rolled_over_minutes = await self._rolled_over_minutes(
                agency_id, brand_id, terms, timezone, period
            )

        included_minutes = terms.retainer_included_minutes + rolled_over_minutes
        remaining_minutes = max(0, included_minutes - used_minutes)
        overage_minutes = max(0, used_minutes - included_minutes)
        overage_cost_cents = 0
        if overage_minutes > 0 and terms.overage_rate_cents is not None:
            overage_cost_cents = round(overage_minutes / 60 * terms.overage_rate_cents)

        if overage_minutes > 0:
            await self._notify_overage_once(agency_id, brand_id, period, overage_minutes)

        return RetainerSummary(
            period_start=period.period_start,
            period_end=period.period_end,
            included_minutes=included_minutes,
            rolled_over_minutes=rolled_over_minutes,
            used_minutes=used_minutes,
            remaining_minutes=remaining_minutes,
            overage_minutes=overage_minutes,
            overage_cost_cents=overage_cost_cents,
            currency=terms.currency,
        )

    async def _notify_overage_once(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID,
        period: RetainerPeriod,
        overage_minutes: int,
    ) -> None:
        """Emits RETAINER_OVERAGE at most once per (brand, period) — this
        method is reached on every read of the retainer summary (e.g. every
        page view / API poll), so the dedupe key must be the period itself,
        not a rolling time window like the scheduler checks use: a given
        (brand_id, period_start) combination is only ever "newly" true once,
        so a single unconditional existence check (no cutoff) is correct and
        sufficient — once notified, this period never notifies again even if
        overage grows further, matching the plan's "once per period"
        instruction. Never includes cost/rate figures — `overage_minutes` is
        a duration, not a price."""
        dedup_key = f"{brand_id}:{period.period_start.isoformat()}"
        stmt = (
            select(NotificationEvent.id)
            .where(
                NotificationEvent.event_type == NotificationEventType.RETAINER_OVERAGE.value,
                func.jsonb_extract_path_text(cast(NotificationEvent.payload, JSONB), "dedup_key")
                == dedup_key,
            )
            .limit(1)
        )
        result = await self._db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            return

        members = await self._member_repo.list_by_agency(agency_id)
        recipient_ids = [
            m.user_id
            for m in members
            if m.status == AgencyMemberStatus.ACTIVE.value
            and Permission.COMMERCIAL_TERMS_VIEW in get_permissions_for_agency_role(m.role)
        ]
        if not recipient_ids:
            return

        await NotificationDispatcher(self._db).emit(
            NotificationEventType.RETAINER_OVERAGE.value,
            payload={
                "dedup_key": dedup_key,
                "period_start": period.period_start.isoformat(),
                "period_end": period.period_end.isoformat(),
                "overage_minutes": overage_minutes,
                "summary": (
                    f"Retainer kullanımı bu dönem için dahil dakikaları "
                    f"{overage_minutes} dakika aştı."
                ),
            },
            agency_id=agency_id,
            brand_id=brand_id,
            actor_user_id=None,
            recipient_ids=recipient_ids,
        )
        await self._db.commit()

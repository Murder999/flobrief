"""TimeTrackingService: timer start/stop, manual entries, locking, and
per-brief estimate/actual/remaining/variance computation.

Only an explicit `start_timer` call or an explicit `create_manual_entry` call
ever creates a TimeEntry row — there is no background/inferred time capture
anywhere in this module (no employee-surveillance features)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.models.brief import Brief
from app.models.enums import NotificationEventType
from app.models.time_entry import TimeEntry
from app.repositories.time_entry import TimeEntryRepository
from app.schemas.time_entry import (
    TimeEntryCreateResult,
    TimeEntryManualCreate,
    TimeEntryStart,
    TimeEntryStop,
    TimeEntryUpdate,
)
from app.schemas.time_report import BriefTimeSummary, CategoryBreakdown

log = logging.getLogger(__name__)


def _duration_seconds(started_at: datetime, ended_at: datetime) -> int:
    return int((ended_at - started_at).total_seconds())


def _as_aware_utc(value: datetime) -> datetime:
    """Normalizes a datetime to timezone-aware UTC for comparison purposes."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class TimeTrackingService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = TimeEntryRepository(db)

    # ── Timer ────────────────────────────────────────────────────────────────

    async def start_timer(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        data: TimeEntryStart,
    ) -> TimeEntry:
        """Starts a new running timer for `user_id`. The DB's partial unique
        index (`uq_time_entry_one_active_per_user`) is the actual correctness
        boundary here, not app-level checking — two concurrent requests both
        reading "no active timer" is exactly the race this guards against."""
        entry = TimeEntry(
            id=uuid.uuid4(),
            agency_id=agency_id,
            brand_id=data.brand_id,
            brief_id=data.brief_id,
            deliverable_id=data.deliverable_id,
            task_id=data.task_id,
            user_id=user_id,
            category=data.category,
            description=data.description,
            started_at=datetime.now(UTC),
            ended_at=None,
            duration_seconds=None,
            billable=data.billable,
            source="timer",
        )
        self._db.add(entry)
        try:
            await self._db.flush()
        except IntegrityError as err:
            await self._db.rollback()
            raise ConflictError("Zaten aktif bir zamanlayıcınız var. Önce onu durdurun.") from err
        await self._db.commit()
        await self._db.refresh(entry)
        return entry

    async def get_active_timer(self, user_id: uuid.UUID) -> TimeEntry | None:
        return await self._repo.get_active_for_user(user_id)

    async def stop_timer(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        entry_id: uuid.UUID,
        data: TimeEntryStop,
        can_manage_peers: bool,
    ) -> TimeEntryCreateResult:
        entry = await self._repo.get_by_id(entry_id, agency_id)
        if entry is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Zaman kaydı", str(entry_id))
        if entry.user_id != user_id and not can_manage_peers:
            from app.core.exceptions import PermissionDeniedError

            raise PermissionDeniedError("Bu zamanlayıcıyı durdurma yetkiniz yok")
        if entry.ended_at is not None:
            raise ConflictError("Bu zamanlayıcı zaten durdurulmuş")
        if entry.locked:
            raise ConflictError("Kilitli bir kayıt değiştirilemez")

        ended_at = datetime.now(UTC)
        entry.ended_at = ended_at
        entry.duration_seconds = _duration_seconds(entry.started_at, ended_at)
        if data.category is not None:
            entry.category = data.category
        if data.description is not None:
            entry.description = data.description
        if data.billable is not None:
            entry.billable = data.billable

        overlap_warning = await self._repo.overlap_check(
            user_id=entry.user_id,
            started_at=entry.started_at,
            ended_at=ended_at,
            exclude_id=entry.id,
        )

        await self._db.commit()
        await self._db.refresh(entry)
        await self._maybe_emit_estimate_overrun(entry)
        return TimeEntryCreateResult(
            entry=entry,  # type: ignore[arg-type]
            overlap_warning=overlap_warning,
        )

    # ── Manual entries ───────────────────────────────────────────────────────

    async def create_manual_entry(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        data: TimeEntryManualCreate,
    ) -> TimeEntryCreateResult:
        now = datetime.now(UTC)
        started_at = _as_aware_utc(data.started_at)
        ended_at = _as_aware_utc(data.ended_at)

        if ended_at > now and not data.confirm_future:
            raise ValidationError(
                "Gelecek tarihli kayıt eklemek için confirm_future=true göndermelisiniz"
            )

        entry = TimeEntry(
            id=uuid.uuid4(),
            agency_id=agency_id,
            brand_id=data.brand_id,
            brief_id=data.brief_id,
            deliverable_id=data.deliverable_id,
            task_id=data.task_id,
            user_id=user_id,
            category=data.category,
            description=data.description,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=_duration_seconds(started_at, ended_at),
            billable=data.billable,
            source="manual",
        )
        self._db.add(entry)
        await self._db.flush()

        overlap_warning = await self._repo.overlap_check(
            user_id=user_id,
            started_at=started_at,
            ended_at=ended_at,
            exclude_id=entry.id,
        )

        await self._db.commit()
        await self._db.refresh(entry)
        await self._maybe_emit_estimate_overrun(entry)
        return TimeEntryCreateResult(
            entry=entry,  # type: ignore[arg-type]
            overlap_warning=overlap_warning,
        )

    async def update_entry(
        self,
        entry: TimeEntry,
        data: TimeEntryUpdate,
    ) -> TimeEntry:
        if entry.locked:
            raise ConflictError("Kilitli bir kayıt değiştirilemez")
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        for key, value in update_data.items():
            setattr(entry, key, value)
        await self._db.commit()
        await self._db.refresh(entry)
        return entry

    async def delete_entry(self, entry: TimeEntry) -> None:
        if entry.locked:
            raise ConflictError("Kilitli bir kayıt silinemez")
        await self._repo.soft_delete(entry)
        await self._db.commit()

    # ── Locking ──────────────────────────────────────────────────────────────

    async def lock_entry(self, entry: TimeEntry, locked_by_id: uuid.UUID) -> TimeEntry:
        if entry.locked:
            raise ConflictError("Kayıt zaten kilitli")
        if entry.ended_at is None:
            raise ConflictError("Devam eden bir zamanlayıcı kilitlenemez")
        locked = await self._repo.lock(entry, locked_by_id)
        await self._db.commit()
        await self._db.refresh(locked)
        return locked

    # ── Estimates ────────────────────────────────────────────────────────────

    async def compute_brief_time_summary(
        self, brief: Brief, agency_id: uuid.UUID
    ) -> BriefTimeSummary:
        entries = await self._repo.list_for_brief(brief.id, agency_id)
        finalized = [e for e in entries if e.duration_seconds is not None]

        actual_hours = (
            round(sum(e.duration_seconds for e in finalized) / 3600, 2) if finalized else 0.0
        )

        by_category: dict[str, list[float | int]] = {}
        for e in finalized:
            bucket = by_category.setdefault(e.category, [0.0, 0])
            bucket[0] += e.duration_seconds / 3600
            bucket[1] += 1

        category_breakdown = [
            CategoryBreakdown(category=cat, hours=round(hours, 2), entry_count=count)
            for cat, (hours, count) in sorted(by_category.items())
        ]

        estimated = brief.estimated_hours
        remaining = round(estimated - actual_hours, 2) if estimated is not None else None
        variance = round(actual_hours - estimated, 2) if estimated is not None else None
        is_over = estimated is not None and actual_hours > estimated

        return BriefTimeSummary(
            brief_id=brief.id,
            estimated_hours=estimated,
            estimated_hours_by_category=brief.estimated_hours_by_category,
            actual_hours=actual_hours,
            remaining_hours=remaining,
            variance_hours=variance,
            is_over_estimate=is_over,
            entry_count=len(finalized),
            category_breakdown=category_breakdown,
        )

    async def _maybe_emit_estimate_overrun(self, entry: TimeEntry) -> None:
        """Emits BRIEF_ESTIMATE_OVERRUN only on the not-over -> over transition,
        synchronously from stop_timer()/create_manual_entry(). Wrapped so a
        notification failure never blocks the time-entry write it's attached to.
        """
        if entry.brief_id is None:
            return
        try:
            brief = await self._db.get(Brief, entry.brief_id)
            if brief is None or brief.estimated_hours is None:
                return

            other_entries = await self._repo.list_for_brief(entry.brief_id, entry.agency_id)
            prior_seconds = sum(e.duration_seconds or 0 for e in other_entries if e.id != entry.id)
            prior_hours = prior_seconds / 3600
            after_hours = prior_hours + (entry.duration_seconds or 0) / 3600

            was_over = prior_hours > brief.estimated_hours
            is_over = after_hours > brief.estimated_hours
            if was_over or not is_over:
                return

            from app.services.notification_dispatcher import NotificationDispatcher

            dispatcher = NotificationDispatcher(self._db)
            await dispatcher.emit(
                NotificationEventType.BRIEF_ESTIMATE_OVERRUN.value,
                payload={
                    "brief_id": str(brief.id),
                    "brief_title": brief.title,
                    "estimated_hours": brief.estimated_hours,
                    "actual_hours": round(after_hours, 2),
                    "summary": (
                        f"'{brief.title}' briefi tahmini süreyi aştı "
                        f"({round(after_hours, 2)}s / {brief.estimated_hours}s)"
                    ),
                },
                agency_id=brief.agency_id,
                brand_id=brief.brand_id,
                actor_user_id=entry.user_id,
            )
        except Exception:
            log.exception("Failed to emit BRIEF_ESTIMATE_OVERRUN for brief %s", entry.brief_id)

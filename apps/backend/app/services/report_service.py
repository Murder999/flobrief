from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval
from app.models.brand import Brand
from app.models.brief import Brief
from app.models.calendar import CalendarItem
from app.models.report import Report, ReportShareToken, ReportSnapshot
from app.repositories.report import (
    ReportRepository,
    ReportShareTokenRepository,
    ReportSnapshotRepository,
)
from app.services.entitlement_service import EntitlementService


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class ReportService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = ReportRepository(db)
        self._snap_repo = ReportSnapshotRepository(db)
        self._token_repo = ReportShareTokenRepository(db)

    async def create_and_generate(
        self,
        agency_id: uuid.UUID,
        report_type: str,
        period_start: date,
        period_end: date,
        title: str,
        created_by_id: uuid.UUID,
        brand_id: uuid.UUID | None = None,
    ) -> tuple[Report, ReportSnapshot]:
        if brand_id is not None:
            brand_result = await self._db.execute(
                select(Brand.id).where(
                    Brand.id == brand_id,
                    Brand.agency_id == agency_id,
                    Brand.deleted_at.is_(None),
                )
            )
            if brand_result.scalar_one_or_none() is None:
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Brand not found in this agency",
                )

        report = await self._repo.create(
            {
                "agency_id": agency_id,
                "brand_id": brand_id,
                "created_by_id": created_by_id,
                "report_type": report_type,
                "period_start": period_start,
                "period_end": period_end,
                "title": title,
                "status": "draft",
            }
        )
        snapshot = await self._generate_snapshot(report)
        await self._repo.update_status(report, "generated")
        await self._db.commit()
        await self._db.refresh(report)
        await self._db.refresh(snapshot)
        return report, snapshot

    async def regenerate(self, report: Report) -> tuple[Report, ReportSnapshot]:
        snapshot = await self._generate_snapshot(report)
        if report.status == "archived":
            await self._repo.update_status(report, "generated")
        await self._db.commit()
        await self._db.refresh(snapshot)
        return report, snapshot

    async def _generate_snapshot(self, report: Report) -> ReportSnapshot:
        metrics = await self._calculate_metrics(
            agency_id=report.agency_id,
            brand_id=report.brand_id,
            period_start=report.period_start,
            period_end=report.period_end,
        )
        return await self._snap_repo.create(report.id, metrics)

    async def _calculate_metrics(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None,
        period_start: date,
        period_end: date,
    ) -> dict:
        start_dt = datetime.combine(period_start, datetime.min.time()).replace(tzinfo=UTC)
        end_dt = datetime.combine(period_end, datetime.max.time()).replace(tzinfo=UTC)

        # ── Brief metrics ──────────────────────────────────────────────────────
        brief_base = [
            Brief.agency_id == agency_id,
            Brief.deleted_at.is_(None),
            Brief.created_at >= start_dt,
            Brief.created_at <= end_dt,
        ]
        if brand_id is not None:
            brief_base.append(Brief.brand_id == brand_id)

        created_q = await self._db.execute(
            select(func.count()).select_from(Brief).where(*brief_base)
        )
        created_briefs_count: int = created_q.scalar_one() or 0

        approved_q = await self._db.execute(
            select(func.count()).select_from(Brief).where(*brief_base, Brief.status == "approved")
        )
        approved_briefs_count: int = approved_q.scalar_one() or 0

        revision_q = await self._db.execute(
            select(func.count())
            .select_from(Brief)
            .where(*brief_base, Brief.status == "revision_requested")
        )
        revision_requested_count: int = revision_q.scalar_one() or 0

        in_review_q = await self._db.execute(
            select(func.count())
            .select_from(Brief)
            .where(*brief_base, Brief.status.in_(("in_review", "ready_for_review")))
        )
        pending_approvals_count: int = in_review_q.scalar_one() or 0

        # ── Most revised briefs (count of revision_requested approvals per brief) ─
        revision_sub = (
            select(Approval.brief_id, Brief.title, func.count().label("rev_count"))
            .join(Brief, Brief.id == Approval.brief_id)
            .where(
                Brief.agency_id == agency_id,
                Brief.deleted_at.is_(None),
                Approval.deleted_at.is_(None),
                Approval.status == "revision_requested",
                Approval.created_at >= start_dt,
                Approval.created_at <= end_dt,
            )
            .group_by(Approval.brief_id, Brief.title)
            .order_by(func.count().desc())
            .limit(5)
        )
        if brand_id is not None:
            revision_sub = revision_sub.where(Brief.brand_id == brand_id)

        rev_rows = await self._db.execute(revision_sub)
        most_revised_briefs = [
            {
                "brief_id": str(row.brief_id),
                "brief_title": row.title,
                "revision_count": row.rev_count,
            }
            for row in rev_rows
        ]

        # ── Average approval time (created → decided_at for approved) ─────────
        avg_stmt = (
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        Approval.decided_at - Approval.created_at,
                    )
                )
            )
            .join(Brief, Brief.id == Approval.brief_id)
            .where(
                Brief.agency_id == agency_id,
                Brief.deleted_at.is_(None),
                Approval.deleted_at.is_(None),
                Approval.status == "approved",
                Approval.decided_at.is_not(None),
                Approval.created_at >= start_dt,
                Approval.created_at <= end_dt,
            )
        )
        if brand_id is not None:
            avg_stmt = avg_stmt.where(Brief.brand_id == brand_id)
        avg_q = await self._db.execute(avg_stmt)
        avg_seconds: float | None = avg_q.scalar_one()
        average_approval_time_hours: float | None = (
            round(avg_seconds / 3600, 2) if avg_seconds is not None else None
        )

        # ── Calendar metrics ───────────────────────────────────────────────────
        cal_base = [
            CalendarItem.agency_id == agency_id,
            CalendarItem.deleted_at.is_(None),
            CalendarItem.publish_at >= start_dt,
            CalendarItem.publish_at <= end_dt,
        ]
        if brand_id is not None:
            cal_base.append(CalendarItem.brand_id == brand_id)

        published_cal_q = await self._db.execute(
            select(func.count())
            .select_from(CalendarItem)
            .where(*cal_base, CalendarItem.status == "published")
        )
        published_calendar_items_count: int = published_cal_q.scalar_one() or 0

        planned_cal_q = await self._db.execute(
            select(func.count())
            .select_from(CalendarItem)
            .where(*cal_base, CalendarItem.status == "planned")
        )
        planned_calendar_items_count: int = planned_cal_q.scalar_one() or 0

        # ── Calendar status distribution ───────────────────────────────────────
        status_dist_q = await self._db.execute(
            select(CalendarItem.status, func.count().label("cnt"))
            .where(*cal_base)
            .group_by(CalendarItem.status)
        )
        calendar_status_distribution = {row.status: row.cnt for row in status_dist_q}

        # ── Platform distribution ──────────────────────────────────────────────
        platform_dist_q = await self._db.execute(
            select(CalendarItem.platform, func.count().label("cnt"))
            .where(*cal_base, CalendarItem.platform.is_not(None))
            .group_by(CalendarItem.platform)
            .order_by(func.count().desc())
        )
        platform_distribution = {row.platform: row.cnt for row in platform_dist_q}

        return {
            "scope_version": 2,
            "created_briefs_count": created_briefs_count,
            "approved_briefs_count": approved_briefs_count,
            "revision_requested_count": revision_requested_count,
            "pending_approvals_count": pending_approvals_count,
            "published_calendar_items_count": published_calendar_items_count,
            "planned_calendar_items_count": planned_calendar_items_count,
            "average_approval_time_hours": average_approval_time_hours,
            "most_revised_briefs": most_revised_briefs,
            "calendar_status_distribution": calendar_status_distribution,
            "platform_distribution": platform_distribution,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }

    async def archive(self, report: Report) -> Report:
        await self._token_repo.revoke_all_for_report(report.id)
        await self._repo.update_status(report, "archived")
        await self._db.commit()
        await self._db.refresh(report)
        return report

    async def create_share_token(
        self,
        report: Report,
        expires_in_days: int = 30,
        allow_pdf_download: bool = True,
    ) -> tuple[ReportShareToken, str]:
        await EntitlementService(self._db).check_feature(
            report.agency_id, "public_report_link_enabled"
        )
        raw_token = secrets.token_urlsafe(48)
        token_hash = _hash_token(raw_token)
        expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
        token = await self._token_repo.create(
            report_id=report.id,
            token_hash=token_hash,
            expires_at=expires_at,
            allow_pdf_download=allow_pdf_download,
        )
        if report.status == "generated":
            await self._repo.update_status(report, "shared")
        await self._db.commit()
        await self._db.refresh(token)
        return token, raw_token

    async def revoke_share_token(self, report: Report, token_id: uuid.UUID) -> ReportShareToken:
        tokens = await self._token_repo.list_for_report(report.id)
        token = next((t for t in tokens if t.id == token_id), None)
        if token is None:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token bulunamadı",
            )
        revoked = await self._token_repo.revoke(token)
        await self._db.commit()
        await self._db.refresh(revoked)
        return revoked

    async def resolve_public_token(
        self, raw_token: str
    ) -> tuple[Report, ReportSnapshot, ReportShareToken]:
        from fastapi import HTTPException, status

        token_hash = _hash_token(raw_token)
        token = await self._token_repo.get_by_hash(token_hash)

        if token is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rapor linki geçersiz",
            )
        now = datetime.now(UTC)
        if token.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Bu rapor linki iptal edilmiştir",
            )
        if token.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Bu rapor linkinin süresi dolmuştur",
            )

        report_result = await self._db.execute(
            select(Report).where(
                Report.id == token.report_id,
                Report.deleted_at.is_(None),
            )
        )
        report = report_result.scalar_one_or_none()
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rapor bulunamadı",
            )

        snapshot = await self._snap_repo.get_latest_for_report(report.id)
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rapor verisi henüz oluşturulmamış",
            )
        return report, snapshot, token

    async def get_with_snapshot(
        self, report_id: uuid.UUID, agency_id: uuid.UUID
    ) -> tuple[Report, ReportSnapshot | None, list[ReportShareToken]]:
        report = await self._repo.get_by_id(report_id, agency_id)
        if report is None:
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rapor bulunamadı")
        snapshot = await self._snap_repo.get_latest_for_report(report.id)
        tokens = await self._token_repo.list_for_report(report.id)
        return report, snapshot, tokens

    async def get_for_brand(
        self, report_id: uuid.UUID, brand_id: uuid.UUID
    ) -> tuple[Report, ReportSnapshot | None]:
        from fastapi import HTTPException, status

        result = await self._db.execute(
            select(Report)
            .join(Brand, Brand.id == Report.brand_id)
            .where(
                Report.id == report_id,
                Report.brand_id == brand_id,
                Report.agency_id == Brand.agency_id,
                Brand.deleted_at.is_(None),
                Report.deleted_at.is_(None),
            )
        )
        report = result.scalar_one_or_none()
        if report is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        snapshot = await self._snap_repo.get_latest_for_report(report.id)
        return report, snapshot

    async def list_for_agency(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None = None,
        report_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Report], int]:
        return await self._repo.list_for_agency(
            agency_id=agency_id,
            brand_id=brand_id,
            report_type=report_type,
            limit=limit,
            offset=offset,
        )

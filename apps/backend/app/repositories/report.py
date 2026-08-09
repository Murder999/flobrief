from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report, ReportShareToken, ReportSnapshot


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict) -> Report:
        report = Report(**data)
        self.session.add(report)
        await self.session.flush()
        return report

    async def get_by_id(self, report_id: uuid.UUID, agency_id: uuid.UUID) -> Report | None:
        result = await self.session.execute(
            select(Report).where(
                Report.id == report_id,
                Report.agency_id == agency_id,
                Report.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_agency(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID | None = None,
        report_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Report], int]:
        stmt = select(Report).where(
            Report.agency_id == agency_id,
            Report.deleted_at.is_(None),
        )
        if brand_id is not None:
            stmt = stmt.where(Report.brand_id == brand_id)
        if report_type is not None:
            stmt = stmt.where(Report.report_type == report_type)
        stmt = stmt.order_by(Report.created_at.desc())

        count_result = await self.session.execute(
            select(Report).where(
                Report.agency_id == agency_id,
                Report.deleted_at.is_(None),
            )
        )
        total = len(count_result.scalars().all())

        paged = stmt.limit(limit).offset(offset)
        result = await self.session.execute(paged)
        return result.scalars().all(), total  # type: ignore[return-value]

    async def update_status(self, report: Report, new_status: str) -> Report:
        report.status = new_status
        await self.session.flush()
        return report

    async def soft_delete(self, report: Report) -> None:
        report.soft_delete()
        await self.session.flush()


class ReportSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, report_id: uuid.UUID, metrics: dict) -> ReportSnapshot:
        snap = ReportSnapshot(report_id=report_id, metrics=metrics)
        self.session.add(snap)
        await self.session.flush()
        return snap

    async def get_latest_for_report(self, report_id: uuid.UUID) -> ReportSnapshot | None:
        result = await self.session.execute(
            select(ReportSnapshot)
            .where(
                ReportSnapshot.report_id == report_id,
                ReportSnapshot.deleted_at.is_(None),
            )
            .order_by(ReportSnapshot.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class ReportShareTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        report_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        allow_pdf_download: bool = True,
    ) -> ReportShareToken:
        token = ReportShareToken(
            report_id=report_id,
            token_hash=token_hash,
            expires_at=expires_at,
            allow_pdf_download=allow_pdf_download,
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> ReportShareToken | None:
        result = await self.session.execute(
            select(ReportShareToken).where(
                ReportShareToken.token_hash == token_hash,
                ReportShareToken.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_report(self, report_id: uuid.UUID) -> list[ReportShareToken]:
        result = await self.session.execute(
            select(ReportShareToken).where(
                ReportShareToken.report_id == report_id,
                ReportShareToken.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def revoke(self, token: ReportShareToken) -> ReportShareToken:
        token.revoked_at = datetime.now(UTC)
        await self.session.flush()
        return token

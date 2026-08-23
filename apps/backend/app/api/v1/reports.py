from __future__ import annotations

import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.core.rbac import Permission
from app.db.session import get_db
from app.schemas.report import (
    PublicReportView,
    ReportCreate,
    ReportListResponse,
    ReportShareTokenCreate,
    ReportShareTokenCreated,
    ReportShareTokenRead,
    ReportSnapshotRead,
    ReportWithSnapshot,
)
from app.services.entitlement_service import EntitlementService
from app.services.report_export_service import ReportExportService
from app.services.report_service import ReportService

report_router = APIRouter(prefix="/reports", tags=["reports"])
public_report_router = APIRouter(prefix="/public/reports", tags=["public-reports"])


def _svc(db: AsyncSession = Depends(get_db)) -> ReportService:
    return ReportService(db)


def _workspace(
    workspace: WorkspaceContext = Depends(get_workspace_context),
) -> WorkspaceContext:
    return workspace


# ── Private endpoints ─────────────────────────────────────────────────────────


@report_router.post("", response_model=ReportWithSnapshot, status_code=201)
async def create_report(
    body: ReportCreate,
    workspace: WorkspaceContext = Depends(_workspace),
    svc: ReportService = Depends(_svc),
) -> ReportWithSnapshot:
    if not workspace.has_permission(Permission.REPORTING_VIEW):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yetki yok")

    report, snapshot = await svc.create_and_generate(
        agency_id=workspace.agency.id,
        report_type=body.report_type,
        period_start=body.period_start,
        period_end=body.period_end,
        title=body.title,
        created_by_id=workspace.user.id,
        brand_id=body.brand_id,
    )
    _, _, tokens = await svc.get_with_snapshot(report.id, workspace.agency.id)
    return ReportWithSnapshot(
        **ReportWithSnapshot.model_validate(report).model_dump(
            exclude={"snapshot", "active_share_tokens"}
        ),
        snapshot=ReportSnapshotRead.model_validate(snapshot),
        active_share_tokens=[ReportShareTokenRead.model_validate(t) for t in tokens],
    )


@report_router.get("", response_model=ReportListResponse)
async def list_reports(
    brand_id: uuid.UUID | None = None,
    report_type: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    workspace: WorkspaceContext = Depends(_workspace),
    svc: ReportService = Depends(_svc),
) -> ReportListResponse:
    if not workspace.has_permission(Permission.REPORTING_VIEW):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yetki yok")

    items, total = await svc.list_for_agency(
        agency_id=workspace.agency.id,
        brand_id=brand_id,
        report_type=report_type,
        limit=limit,
        offset=offset,
    )
    from app.schemas.report import ReportRead

    return ReportListResponse(
        items=[ReportRead.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@report_router.get("/{report_id}", response_model=ReportWithSnapshot)
async def get_report(
    report_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(_workspace),
    svc: ReportService = Depends(_svc),
) -> ReportWithSnapshot:
    if not workspace.has_permission(Permission.REPORTING_VIEW):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yetki yok")

    report, snapshot, tokens = await svc.get_with_snapshot(report_id, workspace.agency.id)
    return ReportWithSnapshot(
        **ReportWithSnapshot.model_validate(report).model_dump(
            exclude={"snapshot", "active_share_tokens"}
        ),
        snapshot=ReportSnapshotRead.model_validate(snapshot) if snapshot else None,
        active_share_tokens=[ReportShareTokenRead.model_validate(t) for t in tokens],
    )


@report_router.post("/{report_id}/regenerate", response_model=ReportWithSnapshot)
async def regenerate_report(
    report_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(_workspace),
    svc: ReportService = Depends(_svc),
) -> ReportWithSnapshot:
    if not workspace.has_permission(Permission.REPORTING_VIEW):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yetki yok")

    report, _ = await svc.get_with_snapshot(report_id, workspace.agency.id)
    report, snapshot = await svc.regenerate(report)
    _, _, tokens = await svc.get_with_snapshot(report.id, workspace.agency.id)
    return ReportWithSnapshot(
        **ReportWithSnapshot.model_validate(report).model_dump(
            exclude={"snapshot", "active_share_tokens"}
        ),
        snapshot=ReportSnapshotRead.model_validate(snapshot),
        active_share_tokens=[ReportShareTokenRead.model_validate(t) for t in tokens],
    )


@report_router.post("/{report_id}/archive", response_model=ReportWithSnapshot)
async def archive_report(
    report_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(_workspace),
    svc: ReportService = Depends(_svc),
) -> ReportWithSnapshot:
    if not workspace.has_permission(Permission.REPORTING_VIEW):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yetki yok")

    report, snapshot, tokens = await svc.get_with_snapshot(report_id, workspace.agency.id)
    archived = await svc.archive(report)
    return ReportWithSnapshot(
        **ReportWithSnapshot.model_validate(archived).model_dump(
            exclude={"snapshot", "active_share_tokens"}
        ),
        snapshot=ReportSnapshotRead.model_validate(snapshot) if snapshot else None,
        active_share_tokens=[ReportShareTokenRead.model_validate(t) for t in tokens],
    )


@report_router.post("/{report_id}/share", response_model=ReportShareTokenCreated, status_code=201)
async def create_share_token(
    report_id: uuid.UUID,
    body: ReportShareTokenCreate,
    workspace: WorkspaceContext = Depends(_workspace),
    svc: ReportService = Depends(_svc),
) -> ReportShareTokenCreated:
    if not workspace.has_permission(Permission.REPORTING_VIEW):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yetki yok")

    report, _, _ = await svc.get_with_snapshot(report_id, workspace.agency.id)
    if report.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arşivlenmiş raporlar paylaşılamaz",
        )
    token, raw = await svc.create_share_token(
        report=report,
        expires_in_days=body.expires_in_days,
        allow_pdf_download=body.allow_pdf_download,
    )
    return ReportShareTokenCreated(
        **ReportShareTokenRead.model_validate(token).model_dump(),
        token=raw,
    )


@report_router.delete("/{report_id}/share/{token_id}", response_model=ReportShareTokenRead)
async def revoke_share_token(
    report_id: uuid.UUID,
    token_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(_workspace),
    svc: ReportService = Depends(_svc),
) -> ReportShareTokenRead:
    if not workspace.has_permission(Permission.REPORTING_VIEW):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yetki yok")

    report, _, _ = await svc.get_with_snapshot(report_id, workspace.agency.id)
    token = await svc.revoke_share_token(report, token_id)
    return ReportShareTokenRead.model_validate(token)


@report_router.get("/{report_id}/pdf")
async def export_pdf(
    report_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(_workspace),
    svc: ReportService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if not workspace.has_permission(Permission.REPORTING_VIEW):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yetki yok")

    await EntitlementService(db).check_feature(workspace.agency.id, "pdf_export_enabled")

    report, snapshot, _ = await svc.get_with_snapshot(report_id, workspace.agency.id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rapor verisi henüz oluşturulmamış",
        )
    pdf_bytes = ReportExportService.build_pdf_bytes(report, snapshot)
    filename = f"postpiloter-report-{report_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Public endpoints (no auth) ────────────────────────────────────────────────


@public_report_router.get("/{token}", response_model=PublicReportView)
async def get_public_report(
    token: str,
    svc: ReportService = Depends(_svc),
) -> PublicReportView:
    report, snapshot, share_token = await svc.resolve_public_token(token)
    return PublicReportView(
        report_type=report.report_type,
        period_start=report.period_start,
        period_end=report.period_end,
        title=report.title,
        metrics=snapshot.metrics,
        narrative=snapshot.narrative,
        generated_at=snapshot.created_at,
        allow_pdf_download=share_token.allow_pdf_download,
    )


@public_report_router.get("/{token}/pdf")
async def download_public_pdf(
    token: str,
    svc: ReportService = Depends(_svc),
) -> StreamingResponse:
    report, snapshot, share_token = await svc.resolve_public_token(token)
    if not share_token.allow_pdf_download:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu link ile PDF indirme yetkisi yok",
        )
    pdf_bytes = ReportExportService.build_pdf_bytes(report, snapshot)
    filename = f"postpiloter-report-{report.id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

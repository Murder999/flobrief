"""Billing API — subscription management, checkout, invoices, entitlements, webhook."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.core.rbac import Permission
from app.db.session import get_db
from app.repositories.plan import PlanRepository
from app.schemas.billing import (
    ChangePlanRequest,
    CheckoutRequest,
    CheckoutResponse,
    EntitlementCheckRequest,
    EntitlementCheckResponse,
    InvoiceRead,
    PlanRead,
    SubscriptionRead,
    UsageSummary,
)
from app.services.billing_service import BillingService
from app.services.entitlement_service import EntitlementService
from app.services.webhook_service import WebhookService

billing_router = APIRouter(prefix="/billing", tags=["billing"])
plans_router = APIRouter(prefix="/plans", tags=["plans"])


def _billing_svc(db: AsyncSession = Depends(get_db)) -> BillingService:
    return BillingService(db)


# ── Public plan listing ───────────────────────────────────────────────────────


@plans_router.get("", response_model=list[PlanRead])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[PlanRead]:
    repo = PlanRepository(db)
    plans = await repo.list_active()
    return [PlanRead.model_validate(p) for p in plans]


# ── Billing subscription ──────────────────────────────────────────────────────


@billing_router.get("/subscription", response_model=SubscriptionRead)
async def get_subscription(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionRead:
    svc = BillingService(db)
    result = await svc.get_subscription(workspace.agency.id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aktif abonelik bulunamadı")
    sub, plan = result
    return SubscriptionRead(
        id=sub.id,
        agency_id=sub.agency_id,
        plan_id=sub.plan_id,
        plan=PlanRead.model_validate(plan),
        status=sub.status,
        billing_provider=sub.billing_provider,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        cancel_at_period_end=sub.cancel_at_period_end,
    )


@billing_router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    if not workspace.has_permission(Permission.BILLING_MANAGE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Fatura yönetim yetkiniz yok")
    svc = BillingService(db)
    data = await svc.create_checkout_session(
        agency_id=workspace.agency.id,
        plan_id=body.plan_id,
        buyer_email=workspace.user.email,
        buyer_name=workspace.user.full_name,
        buyer_id=str(workspace.user.id),
        yearly=body.yearly,
    )
    return CheckoutResponse(**data)


@billing_router.post("/cancel", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def cancel_subscription(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not workspace.has_permission(Permission.BILLING_MANAGE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Fatura yönetim yetkiniz yok")
    svc = BillingService(db)
    await svc.cancel_subscription(workspace.agency.id)


@billing_router.post("/change-plan", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def change_plan(
    body: ChangePlanRequest,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not workspace.has_permission(Permission.BILLING_MANAGE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Fatura yönetim yetkiniz yok")
    svc = BillingService(db)
    await svc.change_plan(workspace.agency.id, body.plan_id)


@billing_router.get("/invoices", response_model=list[InvoiceRead])
async def list_invoices(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[InvoiceRead]:
    if not workspace.has_permission(Permission.BILLING_MANAGE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Fatura yönetim yetkiniz yok")
    svc = BillingService(db)
    invoices = await svc.list_invoices(workspace.agency.id)
    return [InvoiceRead.model_validate(inv) for inv in invoices]


@billing_router.get("/entitlements", response_model=UsageSummary)
async def get_entitlements(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> UsageSummary:
    svc = EntitlementService(db)
    summary = await svc.get_usage_summary(workspace.agency.id)
    return UsageSummary(**summary)


@billing_router.post("/entitlements/check", response_model=EntitlementCheckResponse)
async def check_entitlement(
    body: EntitlementCheckRequest,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> EntitlementCheckResponse:
    svc = EntitlementService(db)
    valid_features = {
        "white_label_enabled",
        "advanced_reporting_enabled",
        "pdf_export_enabled",
        "public_report_link_enabled",
        "whatsapp_infrastructure_enabled",
    }
    if body.feature not in valid_features:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown feature: {body.feature}")
    try:
        await svc.check_feature(workspace.agency.id, body.feature)
        return EntitlementCheckResponse(feature=body.feature, allowed=True)
    except HTTPException as e:
        return EntitlementCheckResponse(feature=body.feature, allowed=False, reason=e.detail)


# ── iyzico Webhook ────────────────────────────────────────────────────────────


@billing_router.post("/webhook/iyzico", status_code=status.HTTP_200_OK)
async def iyzico_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_iyz_signature_v3: str | None = Header(default=None, alias="X-IYZ-SIGNATURE-V3"),
) -> dict[str, str]:
    if not x_iyz_signature_v3:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing webhook signature")

    try:
        payload: dict[str, Any] = await request.json()
    except ValueError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid JSON body") from err

    svc = WebhookService(db)
    if not svc.verify_signature(payload, x_iyz_signature_v3):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")

    event_type: str = payload.get("iyziEventType", "unknown")
    # iyziReferenceCode is the unique ID iyzico assigns per webhook delivery —
    # the correct idempotency key (matches their documented retry behavior of
    # redelivering the *same* notification up to 3 times).
    provider_event_id: str | None = payload.get("iyziReferenceCode")

    await svc.process_event(
        provider="iyzico",
        event_type=event_type,
        provider_event_id=provider_event_id,
        payload=payload,
    )
    return {"status": "ok"}

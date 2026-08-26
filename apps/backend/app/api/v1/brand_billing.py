"""Brand-workspace subscription and billing endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.brand_portal_auth import BrandPortalContext, get_brand_portal_context
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.models.enums import BrandMemberRole
from app.schemas.billing import (
    ChangePlanRequest,
    CheckoutRequest,
    CheckoutResponse,
    InvoiceRead,
    PlanRead,
    SubscriptionRead,
    UsageSummary,
)
from app.services.billing_service import BillingService
from app.services.entitlement_service import EntitlementService

brand_billing_router = APIRouter(prefix="/brand-portal/billing", tags=["brand-billing"])


def _require_brand_billing_owner(ctx: BrandPortalContext) -> None:
    if ctx.membership.role != BrandMemberRole.BRAND_OWNER.value:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Abonelik yönetimi yalnızca marka sahibine aittir",
        )


@brand_billing_router.get("/subscription", response_model=SubscriptionRead)
async def get_brand_subscription(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionRead:
    _require_brand_billing_owner(ctx)
    result = await BillingService(db).get_brand_subscription(ctx.brand.id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aktif abonelik bulunamadı")
    sub, plan = result
    return SubscriptionRead(
        id=sub.id,
        agency_id=sub.agency_id,
        brand_id=sub.brand_id,
        plan_id=sub.plan_id,
        plan=PlanRead.model_validate(plan),
        status=sub.status,
        billing_provider=sub.billing_provider,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        cancel_at_period_end=sub.cancel_at_period_end,
    )


@brand_billing_router.post("/checkout", response_model=CheckoutResponse)
async def create_brand_checkout(
    body: CheckoutRequest,
    request: Request,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    _require_brand_billing_owner(ctx)
    data = await BillingService(db).create_brand_checkout_session(
        brand_id=ctx.brand.id,
        plan_id=body.plan_id,
        buyer_email=ctx.user.email,
        buyer_name=ctx.user.full_name,
        buyer_id=str(ctx.user.id),
        buyer_ip=get_client_ip(request),
        yearly=body.yearly,
    )
    return CheckoutResponse(**data)


@brand_billing_router.post("/cancel", response_model=None)
async def cancel_brand_subscription(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _require_brand_billing_owner(ctx)
    await BillingService(db).cancel_brand_subscription(ctx.brand.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@brand_billing_router.post("/change-plan", response_model=None)
async def change_brand_plan(
    body: ChangePlanRequest,
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _require_brand_billing_owner(ctx)
    await BillingService(db).change_brand_plan(ctx.brand.id, body.plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@brand_billing_router.get("/invoices", response_model=list[InvoiceRead])
async def list_brand_invoices(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[InvoiceRead]:
    _require_brand_billing_owner(ctx)
    invoices = await BillingService(db).list_brand_invoices(ctx.brand.id)
    return [InvoiceRead.model_validate(invoice) for invoice in invoices]


@brand_billing_router.get("/entitlements", response_model=UsageSummary)
async def get_brand_entitlements(
    ctx: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> UsageSummary:
    _require_brand_billing_owner(ctx)
    summary = await EntitlementService(db).get_brand_billing_summary(
        ctx.brand.agency_id, ctx.brand.id
    )
    return UsageSummary(**summary)

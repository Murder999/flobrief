from fastapi import APIRouter

from app.api.v1.accounting_connectors import connector_router
from app.api.v1.activity import activity_router
from app.api.v1.agencies import agency_router
from app.api.v1.approvals import approval_router, public_approval_router
from app.api.v1.assets import asset_router
from app.api.v1.auth import auth_router
from app.api.v1.billing import billing_router, plans_router
from app.api.v1.brand_finance import brand_finance_router
from app.api.v1.brand_identity import brand_identity_router
from app.api.v1.brand_portal import brand_portal_router
from app.api.v1.brand_preview import brand_preview_router
from app.api.v1.branding import branding_router, public_branding_router
from app.api.v1.brands import brand_router
from app.api.v1.brief_tasks import task_router
from app.api.v1.briefs import brief_router
from app.api.v1.calendar import calendar_router
from app.api.v1.capacity import capacity_router
from app.api.v1.comments import comment_router
from app.api.v1.commercial_terms import commercial_terms_router
from app.api.v1.cost_rates import cost_rates_router
from app.api.v1.dashboard import dashboard_router
from app.api.v1.deliverable_preview import preview_router
from app.api.v1.deliverables import deliverable_router
from app.api.v1.demo import demo_router
from app.api.v1.invitations import invitation_router
from app.api.v1.invoices import invoice_router
from app.api.v1.mentions import mention_router
from app.api.v1.notifications import notification_router
from app.api.v1.onboarding import onboarding_router
from app.api.v1.owner import owner_router
from app.api.v1.payments import payment_router
from app.api.v1.platform.router import platform_router
from app.api.v1.profitability import profitability_router
from app.api.v1.public_seo import public_seo_router
from app.api.v1.reports import public_report_router, report_router
from app.api.v1.templates import industry_router, template_router
from app.api.v1.time_entries import brief_time_router, time_entry_router
from app.api.v1.time_reports import time_report_router
from app.api.v1.webhooks import webhook_router
from app.api.v1.workspaces import workspace_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(demo_router)
api_router.include_router(platform_router)
api_router.include_router(plans_router)
api_router.include_router(billing_router)
api_router.include_router(workspace_router)
api_router.include_router(agency_router)
api_router.include_router(brand_router)
api_router.include_router(brand_identity_router)
api_router.include_router(invitation_router)
api_router.include_router(template_router)
api_router.include_router(industry_router)
api_router.include_router(brief_router)
api_router.include_router(calendar_router)
api_router.include_router(approval_router)
api_router.include_router(public_approval_router)
api_router.include_router(comment_router)
api_router.include_router(dashboard_router)
api_router.include_router(deliverable_router)
api_router.include_router(preview_router)
api_router.include_router(task_router)
api_router.include_router(time_entry_router)
api_router.include_router(brief_time_router)
api_router.include_router(time_report_router)
api_router.include_router(capacity_router)
api_router.include_router(commercial_terms_router)
api_router.include_router(cost_rates_router)
api_router.include_router(invoice_router)
api_router.include_router(payment_router)
api_router.include_router(connector_router)
api_router.include_router(profitability_router)
api_router.include_router(asset_router)
api_router.include_router(notification_router)
api_router.include_router(mention_router)
api_router.include_router(onboarding_router)
api_router.include_router(activity_router)
api_router.include_router(owner_router)
api_router.include_router(report_router)
api_router.include_router(public_report_router)
api_router.include_router(branding_router)
api_router.include_router(public_branding_router)
api_router.include_router(public_seo_router)
api_router.include_router(brand_portal_router)
api_router.include_router(brand_finance_router)
api_router.include_router(brand_preview_router)
api_router.include_router(webhook_router)


@api_router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "flobrief-api"}

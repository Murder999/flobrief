"""Platform admin router — aggregates all /platform/* sub-routers."""

from fastapi import APIRouter, Depends

from app.api.v1.platform.agencies import platform_agencies_router
from app.api.v1.platform.analytics import platform_analytics_router
from app.api.v1.platform.auth import platform_auth_router
from app.api.v1.platform.branding import platform_branding_router
from app.api.v1.platform.brands import platform_brands_router
from app.api.v1.platform.demo import platform_demo_router
from app.api.v1.platform.entitlement_overrides import platform_entitlement_overrides_router
from app.api.v1.platform.impersonate import platform_impersonate_router
from app.api.v1.platform.notification_providers import platform_notification_providers_router
from app.api.v1.platform.plans import platform_plans_router
from app.api.v1.platform.seo import platform_growth_router, platform_seo_router
from app.api.v1.platform.subscriptions import platform_subscriptions_router
from app.api.v1.platform.users import platform_users_router
from app.core.dependencies import get_platform_admin_user
from app.models.user import User

platform_router = APIRouter(prefix="/platform", tags=["platform-admin"])

platform_router.include_router(platform_auth_router)
platform_router.include_router(platform_branding_router)
platform_router.include_router(platform_demo_router)
platform_router.include_router(platform_agencies_router)
platform_router.include_router(platform_users_router)
platform_router.include_router(platform_subscriptions_router)
platform_router.include_router(platform_analytics_router)
platform_router.include_router(platform_impersonate_router)
platform_router.include_router(platform_plans_router)
platform_router.include_router(platform_entitlement_overrides_router)
platform_router.include_router(platform_notification_providers_router)
platform_router.include_router(platform_brands_router)
platform_router.include_router(platform_seo_router)
platform_router.include_router(platform_growth_router)


@platform_router.get("/health")
async def platform_health(_admin: User = Depends(get_platform_admin_user)) -> dict[str, str]:
    return {"status": "ok", "scope": "platform-admin"}

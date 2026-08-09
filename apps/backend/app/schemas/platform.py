"""Pydantic schemas for platform admin and owner dashboard endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

# ── MFA ──────────────────────────────────────────────────────────────────────


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_url: str


class MfaConfirmRequest(BaseModel):
    code: str


class MfaConfirmResponse(BaseModel):
    recovery_codes: list[str]
    message: str


class MfaDisableRequest(BaseModel):
    code: str


class MfaVerifyRequest(BaseModel):
    mfa_session_token: str
    code: str


class MfaRecoveryRequest(BaseModel):
    """Use a recovery code instead of TOTP during login."""

    mfa_session_token: str
    recovery_code: str


class MfaRegenerateRequest(BaseModel):
    """Regenerate backup codes after verifying current TOTP."""

    code: str


# ── Platform admin — agencies ─────────────────────────────────────────────────


class PlatformAgencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: str
    owner_user_id: uuid.UUID | None
    plan_id: uuid.UUID | None
    member_count: int
    brand_count: int
    created_at: datetime
    updated_at: datetime


class PlatformAgencyDetail(PlatformAgencyRead):
    subscription_status: str | None
    plan_name: str | None
    plan_code: str | None
    monthly_price_cents: int | None


class AgencySuspendRequest(BaseModel):
    reason: str


class PlatformAgencyUpdate(BaseModel):
    name: str | None = None
    status: str | None = None


class PlatformAgencyMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str | None
    user_full_name: str | None
    role: str
    status: str
    joined_at: datetime | None
    created_at: datetime


class PlatformAgencyUsage(BaseModel):
    brief_total: int
    brief_active: int
    comment_count: int


class PlatformAgencyMemberUpdate(BaseModel):
    role: str | None = None
    status: str | None = None


class PlatformAgencyPlanUpdate(BaseModel):
    plan_id: uuid.UUID
    reason: str | None = None


class PlatformAgencyBrandingRead(BaseModel):
    branding: dict
    domain: dict | None


# ── Platform admin — users ────────────────────────────────────────────────────


class PlatformUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    user_type: str
    is_active: bool
    is_verified: bool
    mfa_enabled: bool
    last_login_at: datetime | None
    created_at: datetime


class PlatformAgencyMembershipRead(BaseModel):
    agency_id: uuid.UUID
    agency_name: str
    role: str
    status: str
    joined_at: datetime | None


class PlatformBrandMembershipRead(BaseModel):
    brand_id: uuid.UUID
    brand_name: str
    agency_id: uuid.UUID | None
    role: str
    status: str
    joined_at: datetime | None


class PlatformUserDetail(PlatformUserRead):
    phone_number: str | None
    whatsapp_opt_in: bool
    is_verified: bool
    agency_memberships: list[PlatformAgencyMembershipRead]
    brand_memberships: list[PlatformBrandMembershipRead]
    brief_created_count: int
    brief_assigned_count: int
    notification_email_enabled: bool | None
    notification_whatsapp_enabled: bool | None
    notification_in_app_enabled: bool | None


class PlatformUserUpdate(BaseModel):
    full_name: str | None = None
    phone_number: str | None = None
    is_active: bool | None = None


# ── Platform admin — brands ───────────────────────────────────────────────────


class PlatformBrandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: str
    agency_id: uuid.UUID | None
    agency_name: str | None
    member_count: int
    brief_count: int
    created_at: datetime
    updated_at: datetime


class PlatformBrandUpdate(BaseModel):
    name: str | None = None
    status: str | None = None


class PlatformBrandMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str | None
    user_full_name: str | None
    role: str
    status: str
    joined_at: datetime | None
    created_at: datetime


# ── Platform admin — subscriptions ───────────────────────────────────────────


class PlatformSubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID | None
    agency_name: str | None
    brand_id: uuid.UUID | None
    plan_id: uuid.UUID
    plan_name: str
    plan_code: str
    status: str
    monthly_price_cents: int
    current_period_start: datetime | None
    current_period_end: datetime | None
    created_at: datetime


class SubscriptionOverrideRequest(BaseModel):
    plan_id: uuid.UUID
    reason: str


# ── Platform admin — dashboard & analytics ────────────────────────────────────


class PlatformDashboardStats(BaseModel):
    total_agencies: int
    active_agencies: int
    suspended_agencies: int
    total_users: int
    active_users_30d: int
    total_subscriptions: int
    mrr_cents: int


class PlatformAnalytics(BaseModel):
    agencies_by_status: dict[str, int]
    users_by_type: dict[str, int]
    plan_distribution: dict[str, int]


# ── Platform admin — audit log ────────────────────────────────────────────────


class PlatformAuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    admin_user_id: uuid.UUID
    action: str
    target_type: str | None
    target_id: uuid.UUID | None
    target_tenant_type: str | None
    target_tenant_id: uuid.UUID | None
    meta: dict | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


# ── Impersonation ─────────────────────────────────────────────────────────────


class ImpersonationResponse(BaseModel):
    access_token: str
    expires_in: int
    impersonated_user_id: str
    impersonated_email: str
    impersonated_user_type: str


class ImpersonateStartRequest(BaseModel):
    reason: str


# ── Owner dashboard ───────────────────────────────────────────────────────────


class OwnerDashboardStats(BaseModel):
    active_brands: int
    active_members: int
    open_briefs: int
    approved_briefs_total: int
    calendar_items_this_month: int


class OwnerMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    role: str
    status: str
    last_login_at: datetime | None
    joined_at: datetime | None
    created_at: datetime


class OwnerSubscriptionRead(BaseModel):
    plan_code: str
    plan_name: str
    plan_description: str | None
    status: str
    max_brands: int | None
    max_users: int | None
    monthly_price_cents: int
    current_period_end: datetime | None
    active_brands: int
    active_members: int


# ── Platform admin — SEO ──────────────────────────────────────────────────────


class PlatformSeoPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_key: str
    title: str | None
    description: str | None
    canonical_url: str | None
    og_title: str | None
    og_description: str | None
    og_image_url: str | None
    twitter_title: str | None
    twitter_description: str | None
    indexable: bool
    follow_links: bool
    updated_at: datetime


class PlatformSeoPageUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    canonical_url: str | None = None
    og_title: str | None = None
    og_description: str | None = None
    og_image_url: str | None = None
    twitter_title: str | None = None
    twitter_description: str | None = None
    indexable: bool | None = None
    follow_links: bool | None = None


class PlatformGrowthSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    google_analytics_id: str | None
    google_tag_manager_id: str | None
    search_console_verification: str | None
    meta_pixel_id: str | None
    linkedin_partner_id: str | None
    robots_txt: str | None
    sitemap_last_generated_at: datetime | None
    public_app_url: str | None


class PlatformGrowthSettingsUpdate(BaseModel):
    google_analytics_id: str | None = None
    google_tag_manager_id: str | None = None
    search_console_verification: str | None = None
    meta_pixel_id: str | None = None
    linkedin_partner_id: str | None = None
    public_app_url: str | None = None


class PlatformRobotsUpdate(BaseModel):
    robots_txt: str


class PlatformSeoAuditIssue(BaseModel):
    severity: str  # critical | high | medium | low
    page_key: str | None
    area: str  # seo_meta | robots | sitemap
    problem: str
    reason: str
    suggestion: str


class PlatformSeoPageInventoryItem(BaseModel):
    page_key: str
    path: str | None
    label: str
    status: str  # published | not_built
    title: str | None
    description: str | None
    canonical_url: str | None
    indexable: bool
    has_og_image: bool
    issue_count: int
    severity: str  # critical | warning | healthy


class PlatformSeoHealthSummary(BaseModel):
    health_score: int
    critical_count: int
    warning_count: int
    indexable_page_count: int
    missing_title_count: int
    missing_description_count: int
    sitemap_configured: bool
    robots_configured: bool
    last_audit_at: str


class PlatformPageSpeedResult(BaseModel):
    url: str
    strategy: str
    performance_score: int | None
    accessibility_score: int | None
    best_practices_score: int | None
    seo_score: int | None
    lcp: str | None
    cls: str | None
    fcp: str | None
    tbt: str | None


class PlatformIntegrationStatus(BaseModel):
    provider: str
    configured: bool
    detail: dict


class PlatformGrowthMetrics(BaseModel):
    total_agencies: int
    active_agencies: int
    total_brands: int
    active_brands: int
    total_users: int
    new_agencies_this_month: int
    new_users_this_month: int
    agencies_with_first_brand: int
    agencies_with_first_brief: int

# Flobrief — 15-Part Development Plan

## Part 1 — Foundation, Monorepo, Docs, UI DNA ✅
Set up monorepo structure, FastAPI skeleton, Next.js skeleton with premium landing screen,
all documentation files, docker-compose, Makefile, git commit.

## Part 2 — Database Core, Multi-Tenant Agency/Brand Schema + platform_admin Foundation
Design and migrate: Agency, Brand, User (user_type kolonu ile), AgencyMember, BrandMember,
Plan, Subscription, PlatformAuditLog tabloları. Multi-tenant isolation pattern, soft-delete,
timestamps. BaseRepository pattern. Seed script (1 agency, 2 tenant_user, 2 brand, 1 platform_admin).
`create_platform_admin.py` CLI bootstrap scripti.

## Part 3 — Auth: JWT, Refresh Token, Password Security, Frontend Auth
Register/login/logout endpoints, bcrypt hashing, JWT access + refresh token rotation
(tenant_user: agency_id + role claim; platform_admin: kısa ömürlü token, user_type claim),
rate limiting on auth routes, frontend login/register pages with form validation.
Platform admin login endpoint ayrı güvenlik katmanında.

## Part 4 — RBAC, Workspace, Invitation, Agency/Brand Members + platform_admin RBAC
Tenant role definitions (agency_owner, agency_admin, agency_member, brand_admin, brand_viewer),
`get_platform_admin_user()` FastAPI dependency, `/api/v1/platform/` router namespace,
workspace context middleware, invitation flow (email token), member management endpoints,
frontend invite flow and member list pages. platform_admin tenant endpoint'lerine erişemez.

## Part 5 — Dynamic Brief Template Engine & Premium Template Builder
BriefTemplate model, section/field schema (JSON), TemplateBuilder UI (drag/reorder sections,
field types: text, textarea, select, multi-select, file, date), template CRUD API.

## Part 6 — Industry Templates, Brief CRUD, Dynamic Form Rendering
Seed industry templates (Social Media, PR, Event, Digital Ad, Influencer),
Brief model, brief creation from template, dynamic form renderer frontend,
brief list/detail pages, status tracking (draft → submitted → in_review).

## Part 7 — Versioning, Approval Backend, Public Approval Portal
BriefVersion model, approval workflow (approve / request_revision),
public approval portal (token-based, no login required for brand reviewer),
premium approval portal UI, revision request with inline comments.

## Part 8 — Comments, Revision Threads, Asset/File Management
Comment model with thread support, revision thread linking to brief sections,
file/asset upload (S3-compatible), file attachment to briefs and comments,
file preview component.

## Part 9 — Premium Content Calendar Backend & Frontend
ContentPost model, calendar CRUD, publish status tracking,
premium calendar UI (month/week view, drag to reschedule, color-coded by status),
filter by brand/platform/status, bulk actions.

## Part 10 — Activity Log, Notification Engine, Mail, WhatsApp Infrastructure
ActivityLog model (tenant-scoped), notification types and in-app notification center,
email notification via SMTP (MailHog in dev), transactional email templates,
passive WhatsApp integration scaffold (webhook-ready, not blocking).

## Part 11 — Reporting, Client Reports, PDF Export, Secure Report Links
Report model, metric aggregation (briefs created, approval rate, avg turnaround),
PDF export (WeasyPrint or reportlab), secure shareable report links (token-based),
premium report page UI with charts.

## Part 12 — White-Label & Premium Agency Branding
AgencyBranding model (logo, colors, custom domain), white-label portal rendering,
CNAME-ready routing logic, brand approval portal with agency theme,
settings page for agency branding configuration.

## Part 13 — Owner / Platform Admin Dashboard, Tenant Management, Platform Analytics, Admin Security
Platform admin panel UI (premium dark, ayrı layout), tüm agency/brand/user/subscription listesi,
tenant suspend/activate/delete, manual subscription override, platform-wide analytics
(MRR, agency count, active user count, churn), MFA/2FA zorunlu kılınması (TOTP),
impersonation (openly logged), platform_audit_logs görüntüleme,
IP allowlist + rate limit konfigürasyonu.

## Part 14 — Plans, Entitlements, iyzico Billing, Subscriptions
Plan model, entitlement matrix (max_brands, max_users, storage_gb, features),
iyzico payment integration, subscription lifecycle (trial → active → past_due → cancelled),
billing portal frontend, usage enforcement middleware.

## Part 15 — Final Premium UX/UI Polish, Security Audit, Tenant Audit, E2E Tests, Deployment Docs, Launch Checklist
Complete all empty/loading/error states across every page, responsive audit (mobile/tablet),
animation and micro-interaction polish, demo seed data for sales demo,
full tenant isolation audit (no cross-tenant data leaks), platform_admin audit log integrity check,
OWASP top-10 review, rate limiting and input validation audit,
Playwright E2E test suite (critical flows: login, brief approval, calendar, admin panel),
deployment guide (Docker + Nginx + SSL), launch checklist document.

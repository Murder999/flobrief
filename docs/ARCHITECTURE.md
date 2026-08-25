# PostPiloter — System Architecture

## Overview
PostPiloter is a multi-tenant B2B SaaS platform. The architecture is designed for:
- Hard tenant isolation (agency-scoped data)
- Role-based access control at the API layer
- Async-first backend for performance
- Stateless API with JWT authentication

## Components

```
┌─────────────────────────────────────────────────────────┐
│                    Client Browser                        │
│              Next.js (TypeScript + Tailwind)             │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS
┌──────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │  Auth    │  │  API v1  │  │ Webhooks │               │
│  │  Routes  │  │  Routes  │  │  Routes  │               │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘               │
│       │              │             │                      │
│  ┌────▼──────────────▼─────────────▼──────────────┐     │
│  │             Service Layer                        │     │
│  │  (business logic, tenant isolation, RBAC check) │     │
│  └────────────────────┬────────────────────────────┘     │
│                       │                                   │
│  ┌────────────────────▼────────────────────────────┐     │
│  │          SQLAlchemy Async ORM                    │     │
│  └──────────┬────────────────────────┬─────────────┘     │
└─────────────┼────────────────────────┼───────────────────┘
              │                        │
┌─────────────▼──────┐   ┌────────────▼──────┐
│    PostgreSQL       │   │      Redis         │
│  (primary store)   │   │  (cache, sessions, │
│                    │   │   task queue)       │
└────────────────────┘   └───────────────────┘
```

## Directory Structure

```
apps/
  backend/
    app/
      main.py           # FastAPI app factory
      core/
        config.py       # Pydantic settings
        security.py     # JWT, password hashing
        dependencies.py # FastAPI dependency injection
      api/
        v1/
          router.py     # API v1 router aggregator
          auth.py       # Auth endpoints
          agencies.py   # Agency management
          brands.py     # Brand management
          briefs.py     # Brief CRUD
          calendar.py   # Content calendar
          reports.py    # Reporting
      db/
        session.py      # Async engine and session factory
        base.py         # Base model with common columns
      models/           # SQLAlchemy ORM models
      schemas/          # Pydantic request/response schemas
      services/         # Business logic per domain
      tests/
    alembic/
      env.py
      versions/
    pyproject.toml
    .env.example

  frontend/
    app/
      layout.tsx        # Root layout
      page.tsx          # Landing / home
      (auth)/           # Auth group: login, register
      (dashboard)/      # Authenticated app
    components/
      ui/               # Design system primitives
      layout/           # Sidebar, header, nav
      briefs/           # Brief-specific components
      calendar/         # Calendar components
      reports/          # Report components
    lib/
      api.ts            # API client (fetch wrapper)
      auth.ts           # Auth helpers
      utils.ts          # General utilities
    styles/
      globals.css       # Tailwind base + custom CSS vars

packages/
  shared/               # Shared types/constants (future)

infra/
  nginx/                # Nginx config (production)

docs/
  ARCHITECTURE.md
  DATABASE.md
  UI_DNA.md
  SECURITY_RULES.md
  DECISIONS.md
```

## User Type Model

Sistemde iki bağımsız kullanıcı katmanı vardır:

```
platform_admin (tenant-independent)
  ├── Tüm Agency'leri yönetir
  ├── Tüm User'ları yönetir
  ├── Tüm Subscription'ları yönetir
  ├── Plan tanımlarını yönetir
  └── platform_audit_logs'a yazar

Agency (tenant root)
  ├── AgencyMember (tenant_user + role)
  ├── Brand (agency-scoped)
  │     └── BrandMember (tenant_user + role)
  ├── BriefTemplate
  ├── Brief → BriefVersion, Comment
  ├── ContentPost
  ├── Report
  └── AgencyBranding
```

`platform_admin` hiçbir agency'e üye değildir. JWT'sinde `agency_id` yoktur.
Tenant endpoint'leri `platform_admin`'in erişimine kapalıdır; yalnızca `/api/v1/platform/` namespace'i açıktır.

## API Design
- Base path: `/api/v1/`
- Auth: Bearer JWT in Authorization header
- Tenant context: resolved from JWT claims (`user_type`, `agency_id`, `role`)
- Platform admin namespace: `/api/v1/platform/` — ayrı dependency ve guard
- Versioning: URL-based (`/v1/`, `/v2/` when needed)
- Pagination: cursor-based for lists
- Error format: `{ "error": { "code": "...", "message": "...", "details": {} } }`

## Authentication Flow
1. POST `/api/v1/auth/login` → returns `access_token` (15min) + `refresh_token` (30d, httpOnly cookie)
2. All API calls: `Authorization: Bearer <access_token>`
3. Token expiry: POST `/api/v1/auth/refresh` → new access_token
4. Logout: POST `/api/v1/auth/logout` → revoke refresh token

### JWT Payload — tenant_user
```json
{ "sub": "<user_id>", "user_type": "tenant_user", "agency_id": "<id>", "role": "agency_owner", "type": "access" }
```

### JWT Payload — platform_admin
```json
{ "sub": "<user_id>", "user_type": "platform_admin", "type": "access" }
```
`agency_id` ve `role` platform_admin token'ında yer almaz.
`create_access_token(subject, extra_claims={...})` mevcut imzası her iki senaryoyu destekler.

## Reporting Architecture (Part 11)

```
ReportService
  ├── create_and_generate(agency_id, ...) → Report + ReportSnapshot
  │     └── _calculate_metrics(db, agency_id, period) → dict
  │           ├── Brief counts (created/approved/revision_requested/pending) — 4 COUNT queries
  │           ├── Average approval time — AVG(EXTRACT(epoch, decided_at - created_at))
  │           ├── Most revised briefs — GROUP BY brief_id ORDER BY COUNT DESC LIMIT 5
  │           ├── Calendar status distribution — GROUP BY status
  │           └── Platform distribution — GROUP BY platform
  ├── create_share_token(report) → (ReportShareToken, raw_token_str)
  │     ├── raw = secrets.token_urlsafe(48)
  │     └── stored = hashlib.sha256(raw.encode()).hexdigest()
  └── resolve_public_token(raw) → (Report, ReportSnapshot, ReportShareToken)
        └── lookup by SHA-256 hash; raises 410 if expired or revoked

ReportExportService
  └── build_pdf_bytes(report, snapshot) → bytes
        ├── _detect_unicode_font() → Arial (Windows) | DejaVuSans (Linux) | None
        ├── TTF path: add_font("MainFont"), set_font("MainFont", ...)
        └── Latin-1 fallback: Helvetica + _s() transliteration
```

Public API: `/api/v1/public/reports/{token}` and `/token/pdf`
- No auth required
- `PublicReportView` response: no agency_id, brand_id, created_by_id, or token_hash
- 410 GONE for expired/revoked tokens

## White-Label Branding Architecture (Part 12)

```
BrandingService
  ├── get_settings(agency_id) → BrandingSettingsRead (upserts default row)
  │     └── _check_entitlement(db, agency_id) → bool
  │           └── SELECT Plan JOIN Subscription WHERE agency_id → plan.white_label_enabled
  ├── update_settings(agency_id, data) → BrandingSettingsRead
  │     └── Raises 403 if is_white_label_enabled=True but entitlement=False
  ├── upload_branding_asset(agency_id, user_id, file, asset_type)
  │     ├── MIME guard: PNG/JPEG/WebP/GIF only (SVG rejected — XSS risk)
  │     ├── Size guard: 5 MB max
  │     ├── storage_key: {agency_id}/branding/{asset_type}/{uuid}.{ext}
  │     ├── Creates Asset + BrandingAsset records
  │     └── Updates settings.{asset_type}_asset_id
  ├── reset_settings(agency_id) → clears all branding fields
  ├── get_public_branding_by_approval_token(raw_token) → PublicBrandingView
  │     ├── SHA-256(raw) → ApprovalToken → Approval → Brief → agency_id
  │     └── Returns is_branded=False if white_label_enabled=False or no entitlement
  ├── get_public_branding_by_report_token(raw_token) → PublicBrandingView
  │     ├── SHA-256(raw) → ReportShareToken (410 if expired/revoked) → Report → agency_id
  │     └── Same safe-default logic as approval token path
  └── create_custom_domain(agency_id, domain) → (raw_token, CustomDomainSettings)
        └── raw = secrets.token_urlsafe(32); hash stored; raw returned once

PublicBrandingView (safe public schema):
  - agency_name, brand_name, primary/secondary/accent_color, logo_url, favicon_url
  - custom_footer_text, is_branded: bool
  - NO agency_id, NO asset_ids, NO internal identifiers
```

Public asset URL: `/api/v1/public/branding/assets/{asset_id}`
- Validates that asset has a BrandingAsset record (prevents arbitrary file exposure)
- Returns FileResponse from local storage (future: CDN URL from S3/R2)

## Background Jobs
- Redis used for task queue (Celery or ARQ — decided in Part 10)
- Email sending, PDF generation, notification dispatch run async
- No synchronous blocking operations in API handlers

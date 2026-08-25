# PostPiloter — Security Rules

## User Types

Sistemde iki mutually-exclusive kullanıcı tipi vardır:

| Tip | `user_type` değeri | Tenant bağlantısı | JWT claims |
|-----|-------------------|-------------------|------------|
| Normal kullanıcı | `tenant_user` | `agency_id` + `role` gerekli | `user_type`, `agency_id`, `role` |
| Platform yöneticisi | `platform_admin` | Yok | sadece `user_type: platform_admin` |

`platform_admin` kullanıcıları:
- Hiçbir zaman `agency_member` veya `brand_member` kaydına sahip olamaz.
- Yalnızca `scripts/create_platform_admin.py` CLI komutu ile oluşturulur — kayıt/davet akışı yoktur.
- Tüm eylemleri `platform_audit_logs` tablosuna yazılır (immutable, UPDATE/DELETE yasak).
- `/api/v1/platform/` prefix'i altındaki endpoint'lere erişir; tenant endpoint'lerine giremez (403).
- Access token ömrü **5 dakika**, refresh token **8 saat** (tenant token'dan kısa).
- MFA/2FA (TOTP) zorunludur — Part 13'te uygulanır.
- IP allowlist opsiyonel: `PLATFORM_ADMIN_IP_ALLOWLIST` env var (CIDR listesi).
- Impersonation açıkça loglanır; sessiz değildir. Bkz. `docs/PLATFORM_ADMIN_SECURITY.md`.

Detaylı platform admin güvenlik kuralları için bkz. `docs/PLATFORM_ADMIN_SECURITY.md`.

## Tenant Isolation
- Every DB query on tenant-scoped tables MUST include `WHERE agency_id = :current_agency_id`
- Service layer functions always receive `agency_id` as explicit parameter — never trust client-supplied IDs without re-validating ownership
- Cross-tenant data access = critical bug, must fail with 403
- Audit query: at Part 15, run automated cross-tenant leak tests for every endpoint

## Authentication
- Passwords: bcrypt with cost factor 12 minimum
- JWT access tokens: tenant_user 15 dakika / platform_admin **5 dakika**, HS256
- Refresh tokens: tenant_user 30 gün / platform_admin **8 saat**, httpOnly cookie
- Refresh token rotation: each refresh invalidates old token, issues new one
- Token revocation: maintain revoked refresh token set in Redis
- Rate limiting on auth endpoints: tenant 10 deneme / 15 dk — platform admin **5 deneme / 10 dk** per IP
- No password reset without email verification
- Email verification required before first login
- Platform admin login: ayrı endpoint `/api/v1/platform/auth/login`

## Authorization (RBAC)

### Tenant Endpoint Checks (her korumalı endpoint)
1. Token geçerli mi?
2. Kullanıcı `tenant_user` tipinde mi?
3. Kullanıcı istenen agency'e üye mi?
4. Kullanıcının rolü bu eyleme izin veriyor mu?

### Platform Admin Endpoint Checks
1. Token geçerli mi?
2. Kullanıcı `platform_admin` tipinde mi? (değilse 403)
3. Eylem `platform_audit_logs`'a yazıldı mı?

### Tenant Role Hierarchy
- `agency_owner` — full access to agency
- `agency_admin` — full access except billing, cannot delete agency
- `agency_member` — read/write briefs and calendar, no settings
- `brand_admin` — view/comment on assigned briefs, manage brand profile
- `brand_viewer` — read-only on assigned briefs

### Platform Admin Capabilities
- Tüm agency'leri listeleme, görüntüleme, askıya alma, silme
- Tüm kullanıcıları listeleme, deaktif etme, silme
- Tüm abonelikleri görüntüleme ve manuel override etme
- Plan tanımlarını yönetme (create/update/deactivate)
- `platform_audit_logs` ve `activity_logs` okuma
- Sistem istatistiklerini görüntüleme

Public endpoints (no auth):
- `GET /api/v1/public/approvals/{token}` — brief approval portal
- `POST /api/v1/public/approvals/{token}/approve|revision|comment` — approval actions
- `GET /api/v1/public/reports/{token}` — secure report link (PublicReportView only)
- `GET /api/v1/public/reports/{token}/pdf` — PDF download (only if allow_pdf_download=True)
- `GET /api/v1/public/branding/by-approval-token/{token}` — agency branding for approval portal
- `GET /api/v1/public/branding/by-report-token/{token}` — agency branding for report page
- `GET /api/v1/public/branding/assets/{asset_id}` — serve branding asset (logo/favicon)

### Public Report Endpoint Security
- Token resolution: SHA-256 hash lookup; raw token never re-stored
- Expired tokens: HTTP 410 GONE (not 401 or 404)
- Revoked tokens: HTTP 410 GONE
- Response schema: `PublicReportView` — contains only report_type, period, title, metrics, narrative, generated_at, allow_pdf_download. NO agency_id, brand_id, created_by_id, or token_hash is leaked.
- PDF endpoint: checks `allow_pdf_download` flag; returns 403 if false

## Input Validation
- All request bodies validated by Pydantic models
- No raw SQL string concatenation — SQLAlchemy parameterized queries only
- File uploads: MIME type validation + size limit (10MB default, configurable per plan)
- URL fields: validated format, no SSRF — disallow private IP ranges
- UUIDs: validate format, never trust as-is without ownership check

## API Security
- CORS: explicit allowlist of frontend origins (no `*` in production)
- Security headers: HSTS, X-Frame-Options, X-Content-Type-Options, CSP
- No sensitive data in URL query params (use POST body or path params)
- Pagination: server-side, never return unbounded lists
- Error messages: no stack traces or internal details in production responses

## Data Protection
- Passwords never logged, never returned in API responses
- JWT secrets in environment variables only, never in code
- Database credentials in environment variables only
- Tenant audit log immutable — no update/delete on `activity_logs`
- Platform audit log immutable — no update/delete on `platform_audit_logs`
- TOTP secrets stored encrypted at rest (`TOTP_ENCRYPTION_KEY` env var)
- File assets stored with unpredictable names (UUID-based paths)

## Frontend Security
- No auth tokens in localStorage — httpOnly cookies for refresh
- No sensitive data in URL hash or query string
- XSS: no `dangerouslySetInnerHTML` unless sanitized with DOMPurify
- CSP headers set server-side

## Approval Portal (Public)
- Token: 64-char cryptographically random string
- Token single-use? No — valid for brief lifetime, but invalidated on brief closure
- Rate limit: 20 actions / hour per token
- No PII in URL (token is opaque identifier only)
- Brief content shown only for the specific approved token's brief

## Dependency Security
- Pin major dependency versions
- Run `pip audit` / `npm audit` before each release
- No unmaintained packages

## Secrets Management
- Development: `.env` file (`.env` in `.gitignore`)
- Staging/Production: environment injection (Docker secrets or cloud secret manager)
- `.env.example` always kept in sync with actual required variables

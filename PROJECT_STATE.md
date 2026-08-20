# Flobrief — Project State

## Status

**Product**: Premium multi-tenant B2B SaaS for agency/brand brief operations
**Current phase**: Production hardening and go-live verification
**Release posture**: Not approved for production until `docs/LAUNCH_CHECKLIST.md` is completed
**Last updated**: 2026-08-21

## Stack

| Layer | Current implementation |
|---|---|
| Backend | Python 3.13, FastAPI 0.115, async SQLAlchemy 2, Alembic, PostgreSQL 16 |
| Frontend | Next.js 14.2, React 18, TypeScript, Tailwind CSS; supported Node runtime 20.x |
| Runtime | Redis 7, Docker Compose, Nginx, persistent local media volume |
| Delivery | Resend HTTPS API, DB-backed encrypted Twilio settings, iyzico |
| Quality | Ruff, Pytest/PostgreSQL integration tests, TypeScript, Next build, Playwright |

## Current Scale

- 84 database tables.
- 50 Alembic migration files; one head required before release.
- 415 API route decorators after duplicate asset routes were removed.
- 100 frontend pages, 112 components, 25 Playwright specs.

## Security Boundaries

- `platform_admin` is tenant-independent, has no `agency_id` claim, and is restricted to `/api/v1/platform/`.
- Tenant endpoints resolve agency/brand membership and apply RBAC before business logic.
- Tenant audit logs and immutable platform audit logs are separate.
- JWT refresh tokens rotate; password changes revoke all refresh sessions.
- Platform access tokens are shorter-lived and platform MFA is separately rate-limited.
- Public approval/report links use revocable hashed tokens.
- iyzico and Twilio webhooks fail closed on missing/invalid signatures.
- Provider credentials are encrypted with `FLOBRIEF_SECRET_ENCRYPTION_KEY`.

## Recent Hardening — 2026-07-27

### PostPiloter Turkish/English internationalization

- English is the global default; Turkish is directly available under `/tr`, with cookie, manual choice, browser language, and country fallback precedence.
- Public, authentication, agency, brand, notification, brief, pricing, profile, password, MFA, email, and shared API-error surfaces use one typed 771-key EN/TR catalog.
- SEO pages publish localized canonical and hreflang metadata; users keep the equivalent public route when switching language.
- User locale is stored through an additive Alembic migration and drives transactional emails and notifications.

### Local development performance

- Local frontend API rewrites target the standard backend port 8000; the stale E2E-only 8003 override was removed.
- `npm run dev` uses Turbopack; `npm run dev:webpack` remains available as a compatibility fallback.
- The global stylesheet now has standards-compliant import ordering, eliminating Turbopack CSS 500 responses.
- Dynamic home metadata falls back after 1.5 seconds when the backend is unavailable.
- Clean-cache home compilation improved from 9.1 seconds to 4.9 seconds; warm requests are approximately 0.3 seconds and API health is below 35 ms locally.

### Real-time notifications

- Agency and brand notification bells use tenant-scoped WebSockets.
- Authentication uses 60-second, single-use Redis tickets; JWTs are not placed in WebSocket URLs.
- Redis pub/sub supports multiple backend workers.
- Signals publish only after transaction commit; rollback publishes nothing.
- Heartbeat, exponential reconnect, visibility/online recovery, and 45-second polling fallback are active.
- Nginx Upgrade forwarding and Docker build-time WebSocket origins are configured.

### Brand portal assets and route integrity

- Removed duplicate `GET` and `POST /brand-portal/briefs/{brief_id}/assets` registrations.
- Added a global regression test that rejects every duplicate HTTP method/path pair.
- Brand asset listing now exposes only `client_visible` and `brand_reference` files.
- Duplicate `AssetLink` rows cannot duplicate list results.
- Brand deletion is restricted to that brand’s own `brand_reference` files.
- Brand reference uploads enforce brief state, preserve image dimensions, notify the agency, and clean storage on transaction failure.

### Runtime and documentation alignment

- Local backend standard is port 8000; PostgreSQL Compose host port is 5433.
- `STORAGE_BACKEND=local` is the only implemented option; S3/R2 remains roadmap work.
- Legacy Meta WhatsApp environment settings were removed; Twilio is DB-backed.
- Resend documentation no longer claims SMTP fallback.
- Standalone Next output is enabled only for Docker/CI; ordinary local builds use native Next output.
- Node 20.x is declared in `package.json` and `.nvmrc`.

### PostPiloter production email and realtime hardening

- Resend remains HTTPS REST-only; production environment credentials are authoritative when present, while DB config remains available outside production and as a no-env fallback.
- Registration verification, verification resend, password reset, agency/team/brand invitations, invitation resend, and notification emails share one provider-resolution and safe delivery-log path.
- Production startup rejects non-PostPiloter public origins, the wrong sender, or Resend test mode; action links use `https://postpiloter.com` and invitation links use `/auth/accept-invite?token=`.
- Nginx and Compose default to `postpiloter.com` / `wss://postpiloter.com`; the existing single-use Redis ticket, post-commit signal, client reconnect, canonical refresh, and polling fallback chain remains intact.

### Public self-service demo

- `/demo` creates a unique, time-limited agency with seeded brands, briefs, and calendar work.
- Demo sessions have durable per-IP quotas, global capacity, optional Turnstile verification, immediate expiry enforcement, and scheduled cleanup.
- External invitations, payments, accounting connections, e-mail, and WhatsApp delivery are suppressed; normal in-product exploration remains available.
- `/platform/demo` controls activation, duration, capacity, daily IP quota, CAPTCHA policy, cleanup, and manual termination.
- Demo tenants, users, and subscriptions are excluded from commercial platform lists, customer metrics, plan distribution, and MRR.

## Part 6A — 2026-07-28: WhatsApp real-provider completion + controlled test send

- Fixed a real bug: `seed_provider_settings.py` wrote `provider="twilio_whatsapp"` while every
  runtime consumer filters on `"whatsapp_twilio"`, making seeded rows invisible.
- `whatsapp_templates` (previously orphaned) is now the approved-template registry: `event_type,
  provider, content_sid, status, variable_schema, updated_by_id, approved_at`. One controlled test
  template (`flobrief_test_notification`) is seeded at `status=draft` — an operator must enter a
  real Twilio Content SID and approve it before any real send is possible.
- `TwilioWhatsAppProvider` gained `send_template_message`, `test_connection`, `get_sender_status`,
  `normalize_provider_error` — connection status (`disabled/not_configured/sandbox/connected/
  degraded/error`) is now a real, persisted check result, never fabricated.
- New tenant Owner/Admin-only `POST /api/v1/notifications/whatsapp/test`: no caller-supplied
  recipient, demo-tenant/consent/phone/template/rate-limit gated, records a real
  `NotificationDelivery` row every time (never a silent no-op).
- `NotificationDeliveryStatus` extended (additive) with queued/accepted/delivered/read and 6
  `skipped_*` reasons; Twilio webhook now parses delivered/read distinctly and sets
  `delivered_at`/`read_at`.
- Real Twilio sandbox credentials are configured locally and verified live (a real, non-sending
  `GET /Accounts/{sid}.json` check succeeded) — the connection is genuinely `connected`, not
  simulated. No real WhatsApp message was sent: no `WHATSAPP_TEST_RECIPIENT` is configured and the
  seeded test template has no approved Content SID yet, so nothing satisfies the no-arbitrary-
  recipient / approved-template-only rules. See `TODO_NEXT.md` for the exact remaining steps.

## Part 6B-1 — 2026-07-28: WhatsApp domain event routing

- `NotificationDispatcher`'s per-event WhatsApp path (previously free-text, per DECISION-050) now
  requires an approved `whatsapp_templates` row — same registry gate as the Part 6A test-send flow.
  No approved template → `skipped_template_missing`; in-app/email are unaffected either way.
- New typed catalog (`whatsapp_event_catalog.py`) maps 16 `NotificationEventType`s to template
  keys; new `whatsapp_payload_builder.py` builds an allowlisted 10-field variable set (HTML-stripped,
  80-char-truncated free text, never a full comment/revision body or cost/rate figure); new
  `whatsapp_recipient_gate.py` narrows WhatsApp-only recipients for `approval.requested` (brand
  `BRIEF_APPROVE`) and `invoice.payment_received` (agency `INVOICE_VIEW`).
  Deterministic per-delivery `idempotency_key` prevents duplicate sends on reprocessing.
- Added 4 new event types (`BRIEF_ASSIGNED`, `BRIEF_OVERDUE`, `INVOICE_DUE_SOON`,
  `INVOICE_PAYMENT_RECEIVED`) with new emit call sites/schedulers; 12 of 16 catalog events reused
  already-correct existing emit sites.
- Migration `n8o9p0q1r2s3` seeds all 16 template codes `status=draft`, `content_sid=NULL` — an
  operator must register real Meta-approved templates before any of them can send.
- 21 new tests (`test_whatsapp_event_dispatch.py`) cover gating, role narrowing, payload
  sanitization, deep links, idempotency, rollback-safety, and the reminder schedulers. See
  `docs/DECISIONS.md` DECISION-082 through DECISION-087.

### Public SEO landing pages — 2026-08-20

- Added `/ajans-programi`, `/musteri-onay-sistemi`, `/revizyon-takip`, `/musteri-portali`, and
  `/online-brief` as static App Router pages with unique metadata, canonical URLs, Open Graph copy,
  one H1 per page, internal linking, and a sitemap fallback that does not depend on the backend.
- All five reuse one responsive public header/footer and server-rendered landing system; only the
  mobile navigation toggle hydrates on the client. Product copy is limited to repo-verified brief,
  comment, revision, deliverable-version, approval, portal, file, and white-label capabilities.
- A 9-test Chromium suite verifies render, public shell, metadata, canonical, indexability, console,
  desktop/mobile overflow, mobile navigation, login-modal behavior, platform-route non-disclosure,
  security headers, and sitemap inclusion.

### Public login and platform-access hardening — 2026-08-20

- Every public login trigger now opens the shared in-page dialog; direct visits to the public login
  entry route also open that dialog and preserve a safe return destination.
- Public headers, footers, auth copy, and tenant-login errors no longer disclose or link the platform
  administration route. Tenant login returns the same generic 401 response for platform accounts.
- Platform pages send `noindex`, `noarchive`, `no-store`, frame-denial, and no-referrer headers;
  `robots.txt` always disallows the platform route even when backend SEO text is customized.
- Live audit finding: both active platform admins still require MFA enrollment, and the production IP
  allowlist is empty. Do not enable either control without tested recovery and a trusted static IP/CIDR.

## Verification Status

| Gate | Current result |
|---|---|
| Duplicate registered routes | PASS — none |
| Focused asset/route regression suite | PASS — 53 tests |
| Demo sandbox and route regression suite | PASS — 9 tests |
| Backend Ruff check + format | PASS — 384 files clean |
| Backend Pytest | PASS — 1777 tests |
| Frontend TypeScript | PASS |
| Frontend lint | PASS — no errors; raw-image optimization warnings remain |
| Frontend production build | PASS — 90/90 static pages generated; Node 20.x remains the release runtime contract |
| SEO landing Playwright suite | PASS — 9/9 on Chromium production build |
| Playwright critical release matrix | PASS — 42/42 on Node 20 production build, current API, PostgreSQL, Redis, and live WebSocket |

## Production Truths

- Local media storage is production data and must remain on the `media_data` volume with off-host backups.
- Resend, Twilio, and iyzico are not production-ready until real credentials and signed delivery flows are verified.
- `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` are frontend build-time values.
- Production readiness is governed by `docs/LAUNCH_CHECKLIST.md`, not by completion of the historical 15-part plan.
- A green push to `main` can deploy the exact verified commit to Hetzner through the guarded `deploy_hetzner` CI job. The job is intentionally inert until the protected GitHub production environment, SSH host identity, server checkout, TLS, and `HETZNER_DEPLOY_ENABLED=true` are configured.
- Hetzner promotion creates on-host PostgreSQL/media backups, applies the one-head migration graph, uses commit-tagged images, waits for health, and attempts application rollback on failure. Database downgrades and restores remain manual, reviewed operations.

## Authoritative Documents

- `AGENTS.md` — engineering rules
- `PART_PLAN.md` — historical 15-part scope
- `PROJECT_STATE.md` — current implemented state
- `TODO_NEXT.md` — unresolved work
- `docs/ENVIRONMENT.md` — exact environment contract
- `docs/DEPLOYMENT.md` — production procedure
- `docs/LAUNCH_CHECKLIST.md` — release gate
- `docs/DECISIONS.md` — architectural decisions

# Flobrief — Next Work

The historical 15-part implementation plan is complete. Production release remains conditional on the readiness checklist.

## Immediate release gates

1. Confirm Alembic has one head and upgrade a clean staging database.
2. Complete every applicable item in `docs/LAUNCH_CHECKLIST.md`.

Completed locally in the latest hardening pass: isolated self-service demo implementation, local Turbopack/API-port performance hardening, five bilingual public SEO landing pages, complete typed EN/TR catalogs and persisted user locale, one shared premium TR/EN home composition with copy-only locale changes, the supplied transparent PostPiloter master logo shared across public and login surfaces, and SVG flag controls, public login-modal and platform-route disclosure hardening, Ruff check/format, backend regression coverage, TypeScript, production build (90/90 static pages), SEO/login/security Chromium checks, the Resend/realtime regression suite, commercial-metric exclusion checks, and the prior critical Playwright release matrix against the current API and live WebSocket.

## Platform access hardening

- Enroll MFA for both active platform administrators and verify recovery codes through a controlled login before enforcement.
- After confirming a stable trusted source address, set `PLATFORM_ADMIN_IP_ALLOWLIST` to the narrowest required static IP/CIDR and test both allowed access and fail-closed rejection. Do not enable it from a changing residential/mobile IP without a recovery path.

## Provider verification

- Install the real `RESEND_API_KEY` only in the untracked production backend environment, keep `RESEND_TEST_MODE=False`, and send controlled verification, invitation, reset, notification, and reconnect smoke tests from `https://postpiloter.com`.
- Confirm `/platform/notifications` reports `configuration_source=environment`. A legacy `email_resend` row may remain for audit history; production environment config is authoritative while its API key is present.
- WhatsApp/Twilio (Part 6A plumbing + Part 6B-1 event routing complete — see PROJECT_STATE.md):
  local Twilio sandbox credentials are already configured and verified live-connected, and all 16
  domain events (brief.created, comment.added, deliverable.*, invoice.*, etc.) now route through the
  approved-template registry via `NotificationDispatcher`. Remaining before any real event message
  can go out: (1) join the Twilio sandbox with a real controlled number ("join <code>" via
  WhatsApp) for dev testing, (2) for each of the 16 seeded `whatsapp_templates` codes that should go
  live, create a real Content Template, get it Meta-approved, then set that row's `content_sid`,
  `variable_schema` (Twilio placeholder number → allowlisted field name, see
  `whatsapp_payload_builder.ALLOWED_VARIABLE_FIELDS`), and `status=approved`. Set exact
  `BACKEND_PUBLIC_URL` for signed webhook delivery in any non-local environment.
- Part 6B-2 (deferred, not started): premium per-category WhatsApp preference UI for end users, and
  an admin template-management screen (currently DB-only via the template registry).
- Verify iyzico sandbox checkout and V3 webhook idempotency, then production merchant credentials.

## Self-service demo activation

- Configure production Cloudflare Turnstile site/secret keys.
- In `/platform/demo`, keep CAPTCHA required, set duration/capacity/per-IP quotas, then explicitly enable the public demo.
- Run two simultaneous public sessions and verify tenant isolation, suppressed external delivery, immediate expiry, cleanup, and commercial-metric exclusion.

## Infrastructure and operations

- Complete the one-time Hetzner/GitHub production-environment setup in `docs/DEPLOYMENT.md`: server deploy user and read-only repository key, populated host-local env files, verified SSH host key, production URL, TLS renewal, and GitHub secrets/variables. Set `HETZNER_DEPLOY_ENABLED=true` only after the first manual release and public health checks pass.
- Configure production DNS, TLS renewal, CORS, `NEXT_PUBLIC_API_URL`, and `NEXT_PUBLIC_WS_URL`.
- Establish off-host PostgreSQL and `media_data` backups; perform a restore drill.
- Add Sentry or equivalent error monitoring and centralized log retention.
- Enable PostgreSQL slow-query monitoring and document alert ownership.
- Implement S3/R2 storage before horizontal deployments that cannot share a durable media volume.

## Test/maintenance follow-up

- Replace `_tmp_media_gallery_e2e_seed.py` with a maintained fixture or remove it.
- Keep `npm run e2e:critical` green for every release; run the broader 166-test/20-spec matrix before major workflow changes.
- Audit raw `<img>` uses: migrate ordinary logos/thumbnails to `next/image` while retaining native elements where canvas, blob URLs, or authenticated media require them.
- Resolve remaining deprecation warnings in JWT/report test dependencies without weakening coverage.

## Deployment sequence

Follow `docs/DEPLOYMENT.md`; do not deploy from this file. The short order is:

1. Populate root `.env` and backend `.env.prod`.
2. Build images with the final public API/WebSocket origins.
3. Back up database and media.
4. Start PostgreSQL/Redis, run migrations and seed plans.
5. Start application services and verify health/critical flows.
6. Bootstrap the platform admin only through the CLI script.

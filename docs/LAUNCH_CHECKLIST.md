# Flobrief Production Readiness Checklist

“Launch ready” means every applicable item below is verified in staging or production—not merely implemented in source.

## Build and code quality

- [ ] FastAPI registered route table contains no duplicate HTTP method/path pairs
- [ ] `ruff check app` passes
- [ ] `ruff format --check app` passes
- [ ] Full `pytest` suite passes against PostgreSQL
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes in CI/Docker Node 20
- [ ] GitHub Actions is green on the exact release commit
- [ ] Alembic reports one head

## Infrastructure and data

- [ ] PostgreSQL 16 uses a strong unique password
- [ ] Redis 7 uses password authentication
- [ ] `DATABASE_URL` and `REDIS_URL` use Docker/service DNS or managed-service hosts, not localhost
- [ ] TLS certificate is installed and auto-renewal is tested
- [ ] Only ports 80, 443, and required administration access are exposed
- [ ] `media_data` is persistent and included in off-host backups
- [ ] Database and media restoration has been tested
- [ ] Health endpoints are monitored

## Secrets and runtime environment

- [ ] `APP_ENV=production` and `APP_DEBUG=false`
- [ ] `SECRET_KEY` is a unique 64+ character secret
- [ ] `TOTP_ENCRYPTION_KEY` and `FLOBRIEF_SECRET_ENCRYPTION_KEY` are independent Fernet keys
- [ ] `PLATFORM_BOOTSTRAP_SECRET` is stored securely and rotated/removed after bootstrap
- [ ] `PLATFORM_ADMIN_IP_ALLOWLIST` matches the production network policy
- [ ] `TRUSTED_PROXY_HOP_COUNT` matches the deployed proxy topology
- [ ] No populated `.env`, `.env.prod`, or `.env.local` file is tracked

## Frontend, CORS, and WebSocket

- [ ] `NEXT_PUBLIC_API_URL` is correct at frontend build time
- [ ] `NEXT_PUBLIC_WS_URL` uses `wss://` and is correct at frontend build time
- [ ] `CORS_ORIGINS` contains only approved HTTPS frontend origins
- [ ] Nginx/proxy forwards WebSocket Upgrade headers
- [ ] WebSocket tickets are single-use and cross-tenant connections receive no signal
- [ ] Notification polling fallback still works when Redis/WebSocket is unavailable
- [ ] White-label and brand portal screens are checked on desktop and mobile

## Authentication and authorization

- [ ] Agency, brand, and platform-admin login/refresh/logout flows pass
- [ ] Platform-admin MFA and recovery codes are verified
- [ ] Platform admin cannot access tenant routes
- [ ] Cross-agency and cross-brand IDOR tests pass
- [ ] Brand asset list hides `internal` assets
- [ ] Brand users cannot delete another brand’s asset
- [ ] Impersonation is visibly disclosed and audited

## Self-service demo

- [ ] Turnstile site and secret keys are configured for the production hostname
- [ ] `/platform/demo` has CAPTCHA required and explicit duration/capacity/IP quotas
- [ ] Two independent demo sessions cannot see each other’s tenant data
- [ ] Demo invitations, billing, payments, invoice sending, accounting connections, email, and WhatsApp are blocked
- [ ] Expired demo access fails immediately and the cleanup scheduler suspends the tenant
- [ ] Manual termination and platform audit-log entries are verified

## Email and WhatsApp

- [ ] Resend test mode delivery succeeds
- [ ] Verified Resend sender domain is active before disabling test mode
- [ ] Twilio credentials are stored encrypted in provider settings
- [ ] `BACKEND_PUBLIC_URL` exactly matches the Twilio webhook origin
- [ ] Twilio signed webhook requests pass and invalid signatures return 401
- [ ] `WHATSAPP_NOTIFICATIONS_ENABLED` is enabled only after verification

## Billing

- [ ] iyzico sandbox checkout → signed webhook → subscription activation passes
- [ ] Production merchant account and credentials are approved
- [ ] `IYZICO_BASE_URL=https://api.iyzipay.com`
- [ ] `X-IYZ-SIGNATURE-V3` is enabled for the merchant
- [ ] Production webhook is `https://<domain>/api/v1/billing/webhook/iyzico`
- [ ] Duplicate webhook delivery is idempotent

## Database initialization

- [ ] `alembic upgrade head` completed
- [ ] `scripts/seed_plans.py` completed
- [ ] Platform admin was created only through `scripts/create_platform_admin.py`
- [ ] Legacy fixed sales-demo accounts are absent from production; only isolated expiring sandboxes are allowed

## Observability and go-live

- [ ] Error monitoring is configured (Sentry or equivalent)
- [ ] Nginx/application logs are centralized with retention
- [ ] PostgreSQL slow-query monitoring is enabled
- [ ] Alert ownership and incident contacts are documented
- [ ] Staging approval/revision, calendar, files, notifications, billing, and provider flows pass end to end
- [ ] Rollback owner, database restore point, and previous image tags are recorded

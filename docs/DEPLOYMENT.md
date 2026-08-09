# Flobrief Production Deployment

This guide covers the repository’s Docker Compose topology: Nginx → Next.js/FastAPI, PostgreSQL 16, Redis 7, and a persistent local-media volume.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- Production domain and DNS
- TLS certificate and private key
- Resend account and verified sender domain
- Production iyzico credentials when billing is enabled
- Twilio WhatsApp sender when WhatsApp delivery is enabled

S3/R2 storage is not implemented. The `media_data` Docker volume is production data and requires backups.

## 1. Prepare configuration

```bash
git clone <repository-url>
cd flobrief
cp .env.example .env
cp apps/backend/.env.example apps/backend/.env.prod
```

Set root `.env` values used by Compose:

```dotenv
POSTGRES_USER=flobrief
POSTGRES_PASSWORD=<strong-database-password>
POSTGRES_DB=flobrief
REDIS_PASSWORD=<strong-redis-password>
NEXT_PUBLIC_API_URL=https://flobrief.example
NEXT_PUBLIC_WS_URL=wss://flobrief.example
```

Set backend `apps/backend/.env.prod`:

```dotenv
APP_ENV=production
APP_DEBUG=false
SECRET_KEY=<unique-64+-character-secret>
DATABASE_URL=postgresql+asyncpg://flobrief:<database-password>@postgres:5432/flobrief
REDIS_URL=redis://:<redis-password>@redis:6379/0
MEDIA_ROOT=/app/media
STORAGE_BACKEND=local
FRONTEND_URL=https://flobrief.example
FRONTEND_PUBLIC_URL=https://flobrief.example
BACKEND_PUBLIC_URL=https://flobrief.example
CORS_ORIGINS=https://flobrief.example
PLATFORM_BOOTSTRAP_SECRET=<one-time-bootstrap-secret>
TOTP_ENCRYPTION_KEY=<fernet-key>
FLOBRIEF_SECRET_ENCRYPTION_KEY=<different-fernet-key>
DEMO_SANDBOX_TURNSTILE_SITE_KEY=<cloudflare-turnstile-site-key>
DEMO_SANDBOX_TURNSTILE_SECRET_KEY=<cloudflare-turnstile-secret-key>
DEMO_SANDBOX_CLEANUP_INTERVAL_SECONDS=300
```

Also configure Resend and iyzico values described in `docs/ENVIRONMENT.md`. Do not use sandbox iyzico credentials for live traffic.

## 2. Configure TLS and Nginx

Place:

```text
infra/nginx/certs/fullchain.pem
infra/nginx/certs/privkey.pem
```

Replace `flobrief.com` / `www.flobrief.com` in `infra/nginx/nginx.conf` with the production hosts. Keep the exact `/api/v1/notifications/realtime` WebSocket location and its Upgrade headers.

## 3. Build with public frontend variables

```bash
docker compose -f docker-compose.prod.yml build --pull
```

The public API and WebSocket origins are build arguments. Rebuild the frontend whenever either changes.

## 4. Start infrastructure and migrate

```bash
docker compose -f docker-compose.prod.yml up -d postgres redis
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.prod.yml run --rm backend python scripts/seed_plans.py
docker compose -f docker-compose.prod.yml up -d
```

Never modify the schema manually. Confirm the migration graph has one head before deployment:

```bash
docker compose -f docker-compose.prod.yml run --rm backend alembic heads
```

## 5. Bootstrap the platform admin

```bash
docker compose -f docker-compose.prod.yml exec backend \
  python scripts/create_platform_admin.py
```

The script is the only supported platform-admin creation path.

## 6. Configure delivery providers

- Add Resend and Twilio credentials through the platform notification-provider screen so secrets are encrypted in the database.
- Keep `RESEND_TEST_MODE=true` until test delivery succeeds.
- Set `WHATSAPP_NOTIFICATIONS_ENABLED=true` only after Twilio credentials and webhook signatures are verified.
- Register `https://<domain>/api/v1/webhooks/twilio/whatsapp` in Twilio.
- Register `https://<domain>/api/v1/billing/webhook/iyzico` in iyzico and require V3 signatures.

## 7. Enable the self-service demo

1. Create a Cloudflare Turnstile widget for the production frontend hostname.
2. Add its site and secret keys to `apps/backend/.env.prod`, then restart the backend.
3. Open `/platform/demo` as a platform admin.
4. Keep CAPTCHA required, set the duration, concurrent capacity, and per-IP daily quota.
5. Enable the public demo and verify `/demo` in a private browser session.

The production default is disabled. Do not disable CAPTCHA for a public deployment. Demo tenants suppress external email/WhatsApp delivery and block invitations, billing, payments, invoice sending, and accounting connections.

## Verification

```bash
curl -fsS https://<domain>/api/v1/health
curl -fsS https://<domain>/
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=200 backend nginx
```

Verify in a browser:

- Agency and brand login/refresh
- Brief creation and approval/revision flow
- Brand reference upload/list/delete
- Notification bell opens one WebSocket connection and updates without waiting for polling
- Resend test delivery
- Twilio signed webhook delivery
- iyzico signed webhook flow
- Public `/demo` creates a unique tenant, reaches the seeded dashboard, blocks external actions, and expires on schedule

## Updates and rollback preparation

Before promotion:

```bash
python -m ruff check apps/backend
python -m pytest -q apps/backend/app/tests
cd apps/frontend && npm ci && npm run typecheck && npm run build
```

Build the new images, back up database/media, run migrations, then replace services:

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.prod.yml up -d --no-deps backend frontend nginx
```

Database rollback is migration-specific. Do not downgrade automatically after new code has written data; use the documented backup and a reviewed rollback plan.

## Backups

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U flobrief flobrief | gzip > flobrief-db-$(date +%Y%m%d).sql.gz

docker compose -f docker-compose.prod.yml exec -T backend \
  tar -C /app -czf - media > flobrief-media-$(date +%Y%m%d).tar.gz
```

Store backups outside the Docker host and test restoration regularly.

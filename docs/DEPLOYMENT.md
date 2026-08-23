# Flobrief Production Deployment

This guide covers the repository’s Docker Compose topology on Hetzner: Nginx → Next.js/FastAPI, PostgreSQL 16, Redis 7, and a persistent local-media volume. A successful CI run on `main` can promote the exact tested commit automatically; deployment remains disabled until the production environment is configured explicitly.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- Production domain and DNS
- TLS certificate and private key
- Resend account and verified sender domain
- Production iyzico credentials when billing is enabled
- Twilio WhatsApp sender when WhatsApp delivery is enabled

S3/R2 storage is not implemented. The `media_data` Docker volume is production data and requires backups.

## Automated GitHub → Hetzner delivery

The `deploy_hetzner` job in `.github/workflows/ci.yml` runs only when all of the following are true:

- The event is a push to `main`.
- Backend Ruff/Pytest and frontend TypeScript/build jobs both pass.
- Repository variable `HETZNER_DEPLOY_ENABLED` is exactly `true`.

The job connects with strict SSH host-key checking and sends `scripts/deploy_hetzner.sh` to the server. The server then verifies the repository remote and commit, backs up PostgreSQL and local media, builds commit-tagged images, verifies that Alembic has one head, applies migrations, seeds plans idempotently, replaces application containers, waits for container health, and checks the public frontend/API. Concurrent production deployments are locked. If the new application containers fail, the script attempts an application-image rollback; it never performs an automatic Alembic downgrade or database restore.

### One-time Hetzner preparation

1. Install Git, Docker Engine 24+, Docker Compose v2, `curl`, `flock`, `gzip`, and `sha256sum` on the server.
2. Create a non-root deploy user with SSH-key login and permission to use Docker. Disable password SSH authentication after key access is verified.
3. Clone `git@github.com:Murder999/flobrief.git` into a dedicated path such as `/opt/flobrief`. Give the server a read-only GitHub deploy key because every deployment fetches the exact CI-tested commit.
4. Create `/opt/flobrief/.env` and `/opt/flobrief/apps/backend/.env.prod` from the tracked examples, with production-only values.
5. Install the TLS files at `/opt/flobrief/infra/nginx/certs/fullchain.pem` and `privkey.pem`. Configure and test certificate renewal outside the repository before enabling automatic deployment.
6. Run the manual first deployment in this document and confirm the public health endpoints.

Create a protected GitHub environment named `production`, then configure:

| Type | Name | Value |
|---|---|---|
| Secret | `HETZNER_HOST` | Server DNS name or IPv4 address |
| Secret | `HETZNER_SSH_USER` | Non-root deploy user |
| Secret | `HETZNER_SSH_PRIVATE_KEY` | Private key dedicated to GitHub Actions → Hetzner |
| Secret | `HETZNER_KNOWN_HOSTS` | Trusted `known_hosts` line captured after fingerprint verification |
| Variable | `HETZNER_SSH_PORT` | SSH port; blank means `22` |
| Variable | `HETZNER_APP_DIR` | Absolute checkout path, for example `/opt/flobrief` |
| Variable | `PRODUCTION_URL` | HTTPS origin only, for example `https://app.example.com` |
| Variable | `HETZNER_DEPLOY_ENABLED` | Set to `true` only after the manual deployment passes |

Generate the known-host entry from a trusted network and compare the fingerprint with Hetzner before storing it:

```bash
ssh-keyscan -p 22 <hetzner-host>
```

Do not replace `HETZNER_KNOWN_HOSTS` with runtime `ssh-keyscan` in CI; doing so would remove host identity verification. Do not store application secrets in GitHub deployment variables—the populated `.env` files remain only on the server.

## 1. Prepare configuration

```bash
git clone git@github.com:Murder999/flobrief.git
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
NEXT_PUBLIC_API_URL=https://postpiloter.com
NEXT_PUBLIC_WS_URL=wss://postpiloter.com
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
FRONTEND_URL=https://postpiloter.com
FRONTEND_PUBLIC_URL=https://postpiloter.com
BACKEND_PUBLIC_URL=https://postpiloter.com
CORS_ORIGINS=https://postpiloter.com
RESEND_API_KEY=<server-secret>
EMAIL_FROM=noreply@postpiloter.com
EMAIL_FROM_NAME=PostPiloter
EMAIL_REPLY_TO=
RESEND_TEST_MODE=False
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

Nginx is configured for `postpiloter.com` / `www.postpiloter.com`. Keep the exact `/api/v1/notifications/realtime` WebSocket location and its Upgrade headers.

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

After the one-time GitHub/Hetzner configuration above, normal releases do not use these manual update commands: a green push to `main` invokes the same guarded sequence automatically. The server records the successful SHA in `.deploy/current-release`, and pre-deploy backups are stored under `backups/<timestamp>-<previous-sha>/`. These on-host backups are a recovery aid, not a substitute for the mandatory off-host backup policy.

## Backups

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U flobrief flobrief | gzip > flobrief-db-$(date +%Y%m%d).sql.gz

docker compose -f docker-compose.prod.yml exec -T backend \
  tar -C /app -czf - media > flobrief-media-$(date +%Y%m%d).tar.gz
```

Store backups outside the Docker host and test restoration regularly.

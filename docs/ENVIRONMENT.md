# PostPiloter Environment Reference

PostPiloter uses three separate environment surfaces:

- Root `.env`: Docker Compose interpolation (`POSTGRES_PASSWORD`, `REDIS_PASSWORD`, public frontend build variables).
- `apps/backend/.env` or `.env.prod`: FastAPI runtime settings.
- `apps/frontend/.env.local`: local Next.js build/runtime settings. `NEXT_PUBLIC_*` values are compiled into the browser bundle and must be present at build time.
- `apps/frontend/.env.paddle` (optional, ignored): local Paddle public client token and Price IDs loaded by the frontend npm scripts when provider values are kept separate from `.env.local`.

Never commit populated `.env`, `.env.prod`, or `.env.local` files.

Sanitised `.env.example` files are intentionally version-controlled. The root `.gitignore` keeps those examples while ignoring every populated environment file. Hetzner deployment connection settings live in the protected GitHub `production` environment and are documented in `docs/DEPLOYMENT.md`; application secrets remain in the server-local environment files.

## Application and authentication

| Variable | Required | Default | Description |
|---|---:|---|---|
| `APP_NAME` | No | `PostPiloter` | Application name |
| `APP_ENV` | Production | `development` | Set to `production` in production |
| `APP_DEBUG` | No | `false` | Enables API docs when true |
| `SECRET_KEY` | **Yes** | — | Unique 64+ character JWT signing secret |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `15` | Tenant access-token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `30` | Tenant refresh-token lifetime |
| `APPROVAL_TOKEN_EXPIRE_HOURS` | No | `72` | Public approval token lifetime |

## Platform security

| Variable | Required | Default | Description |
|---|---:|---|---|
| `PLATFORM_ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `5` | Platform access-token lifetime |
| `PLATFORM_ADMIN_REFRESH_TOKEN_EXPIRE_HOURS` | No | `8` | Platform refresh-token lifetime |
| `PLATFORM_ADMIN_RATE_LIMIT_ATTEMPTS` | No | `5` | Platform login attempts per window |
| `PLATFORM_ADMIN_RATE_LIMIT_WINDOW_SECONDS` | No | `600` | Platform login window |
| `PLATFORM_ADMIN_MFA_RATE_LIMIT_ATTEMPTS` | No | `5` | MFA attempts per window |
| `PLATFORM_ADMIN_MFA_RATE_LIMIT_WINDOW_SECONDS` | No | `600` | MFA window |
| `PLATFORM_ADMIN_IP_ALLOWLIST` | No | empty | Comma-separated IP/CIDR allowlist |
| `PLATFORM_BOOTSTRAP_SECRET` | **Yes in production** | empty | First-admin CLI bootstrap secret |
| `TOTP_ENCRYPTION_KEY` | **Yes in production** | empty | Fernet key for TOTP secrets |
| `FLOBRIEF_SECRET_ENCRYPTION_KEY` | **Yes for provider settings** | empty | Fernet key for encrypted Resend/Twilio credentials |
| `TRUSTED_PROXY_HOP_COUNT` | No | `1` | Trusted reverse-proxy hops counted from the right of `X-Forwarded-For` |

Generate Fernet keys with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Database and Redis

| Variable | Required | Default | Description |
|---|---:|---|---|
| `DATABASE_URL` | **Yes** | — | Async SQLAlchemy URL (`postgresql+asyncpg://...`) |
| `DATABASE_POOL_SIZE` | No | `10` | SQLAlchemy pool size |
| `DATABASE_MAX_OVERFLOW` | No | `20` | SQLAlchemy overflow connections |
| `REDIS_URL` | **Yes in production** | `redis://localhost:6379/0` | Rate limit, WebSocket ticket, and pub/sub connection |
| `NOTIFICATION_WS_TICKET_TTL_SECONDS` | No | `60` | Single-use WebSocket ticket lifetime |
| `NOTIFICATION_WS_HEARTBEAT_SECONDS` | No | `25` | Application heartbeat interval |
| `NOTIFICATION_WS_RECONNECT_DELAY_SECONDS` | No | `2` | Backend Redis subscriber retry delay |

Docker Compose service URLs use service names, not localhost:

```dotenv
DATABASE_URL=postgresql+asyncpg://flobrief:<password>@postgres:5432/flobrief
REDIS_URL=redis://:<redis-password>@redis:6379/0
```

## Public origins and CORS

| Variable | Required | Default | Description |
|---|---:|---|---|
| `FRONTEND_URL` | Production | `http://localhost:3000` | Must be `https://postpiloter.com` in production |
| `FRONTEND_PUBLIC_URL` | Production | `http://localhost:3000` | Must be `https://postpiloter.com`; source for email and notification action links |
| `BACKEND_PUBLIC_URL` | Production | empty | Must be `https://postpiloter.com`; also used for Twilio signature verification |
| `CORS_ORIGINS` | Production | `http://localhost:3000` | Comma-separated browser origins |
| `CORS_ALLOW_CREDENTIALS` | No | `true` | Credentialed CORS requests |
| `NEXT_PUBLIC_API_URL` | Frontend build | `http://localhost:8000` | Public API origin; may equal the frontend origin behind Nginx |
| `NEXT_PUBLIC_WS_URL` | Frontend build | `ws://localhost:8000` | WebSocket origin; use `wss://` in production |
| `NEXT_PUBLIC_APP_NAME` | No | `PostPiloter` | Browser application name |
| `NEXT_PUBLIC_PADDLE_CLIENT_TOKEN` | Pricing/checkout | — | Browser-facing Paddle client token; `live_` selects production and `test_` selects sandbox |
| `NEXT_PUBLIC_PADDLE_PRICE_BRAND_SOLO_MONTHLY` | Pricing/checkout | — | Brand Solo monthly Paddle Price ID |
| `NEXT_PUBLIC_PADDLE_PRICE_BRAND_SOLO_YEARLY` | Pricing/checkout | — | Brand Solo yearly Paddle Price ID |
| `NEXT_PUBLIC_PADDLE_PRICE_STARTER_AGENCY_MONTHLY` | Pricing/checkout | — | Starter Agency monthly Paddle Price ID |
| `NEXT_PUBLIC_PADDLE_PRICE_STARTER_AGENCY_YEARLY` | Pricing/checkout | — | Starter Agency yearly Paddle Price ID |
| `NEXT_PUBLIC_PADDLE_PRICE_PRO_AGENCY_MONTHLY` | Pricing/checkout | — | Pro Agency monthly Paddle Price ID |
| `NEXT_PUBLIC_PADDLE_PRICE_PRO_AGENCY_YEARLY` | Pricing/checkout | — | Pro Agency yearly Paddle Price ID |
| `NEXT_PUBLIC_PADDLE_PRICE_AGENCY_PLUS_MONTHLY` | Pricing/checkout | — | Agency Plus monthly Paddle Price ID |
| `NEXT_PUBLIC_PADDLE_PRICE_AGENCY_PLUS_YEARLY` | Pricing/checkout | — | Agency Plus yearly Paddle Price ID |

All `NEXT_PUBLIC_*` values above are Docker build arguments in `docker-compose.prod.yml`; changing only the running container environment does not rewrite an already-built browser bundle. Production Compose fails before building if a required Paddle public value is absent. Docker Compose does not discover `.env.paddle` automatically, so the guarded Hetzner deploy script explicitly loads both the root `.env` and `.env.paddle` before build, rollback, and diagnostics commands.

## Self-service demo sandbox

| Variable | Required | Default | Description |
|---|---:|---|---|
| `DEMO_SANDBOX_TURNSTILE_SITE_KEY` | Public demo with CAPTCHA | empty | Cloudflare Turnstile browser-facing site key |
| `DEMO_SANDBOX_TURNSTILE_SECRET_KEY` | Public demo with CAPTCHA | empty | Server-side Turnstile verification secret |
| `DEMO_SANDBOX_CLEANUP_INTERVAL_SECONDS` | No | `300` | Expired sandbox cleanup interval; minimum effective value is 30 seconds |

The feature is disabled by default. A platform admin controls activation, duration, concurrent capacity, per-IP daily quota, and CAPTCHA policy at `/platform/demo`. When CAPTCHA is required, the backend refuses to enable the feature until both Turnstile keys are configured.

Each visitor receives a separate agency and synthetic verified user. Demo tenants have a fixed expiry, are suspended automatically, and cannot send external email/WhatsApp messages, create invitations, initiate billing, or connect accounting/payment providers.

## Email (Resend)

| Variable | Required | Default | Description |
|---|---:|---|---|
| `RESEND_API_KEY` | Production delivery | empty | Server secret; authoritative in production when set, never commit it |
| `RESEND_TEST_MODE` | No | `false` | Routes messages to the Resend test recipient; production validation requires `false` |
| `RESEND_TEST_RECIPIENT` | No | `delivered@resend.dev` | Test-mode destination |
| `RESEND_TEST_FROM_EMAIL` | No | `onboarding@resend.dev` | Test-mode sender |
| `EMAIL_FROM` | Production delivery | `noreply@postpiloter.com` | Production validation requires this verified sender |
| `EMAIL_FROM_NAME` | Production delivery | `PostPiloter` | Production sender display name |
| `EMAIL_REPLY_TO` | No | empty | Optional reply-to |

Production code uses the Resend HTTPS API and has no SMTP fallback. When a production
`RESEND_API_KEY` is present, environment configuration is authoritative so a stale,
disabled, incomplete, or invalid DB row cannot replace the server-managed credential.
Without a production environment key, an enabled/decryptable `email_resend` DB row is
used. Outside production, the valid enabled DB row is preferred and environment config
is the fallback.

## WhatsApp (Twilio)

| Variable | Required | Default | Description |
|---|---:|---|---|
| `WHATSAPP_NOTIFICATIONS_ENABLED` | Delivery | `false` | Global delivery kill switch |
| `BACKEND_PUBLIC_URL` | Webhooks | empty | Must match the Twilio webhook origin exactly |
| `FRONTEND_PUBLIC_URL` | Links | local frontend | Public links placed in WhatsApp messages |

Twilio Account SID, Auth Token, and sender number are stored encrypted in the database through the platform notification-provider screen. Legacy Meta Graph API environment variables are not used.

Webhook URL:

```text
https://<domain>/api/v1/webhooks/twilio/whatsapp
```

## Storage

| Variable | Required | Default | Description |
|---|---:|---|---|
| `STORAGE_BACKEND` | No | `local` | Only `local` is currently implemented |
| `MEDIA_ROOT` | Production | `./media` | Persistent asset root (`/app/media` in Docker) |
| `MAX_UPLOAD_SIZE_MB` | No | `10` | Upload size limit |

S3/R2 is roadmap work, not a selectable production backend. Production local storage must use the `media_data` persistent volume and must be included in backups.

## Billing (iyzico)

| Variable | Required | Default | Description |
|---|---:|---|---|
| `IYZICO_API_KEY` | Live billing | empty | iyzico API key |
| `IYZICO_SECRET_KEY` | Live billing | empty | API secret and V3 webhook verification secret |
| `IYZICO_MERCHANT_ID` | Live billing | empty | Merchant ID |
| `IYZICO_BASE_URL` | No | sandbox URL | Use `https://api.iyzipay.com` in production |

The merchant must send `X-IYZ-SIGNATURE-V3`; missing or invalid signatures fail closed with HTTP 401.

## Optional SEO integrations

`PAGESPEED_API_KEY`, `GOOGLE_SEARCH_CONSOLE_PROPERTY_URL`, `GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_EMAIL`, `GA4_PROPERTY_ID`, and `GA4_SERVICE_ACCOUNT_EMAIL` are optional. Empty values must remain visibly “not configured”; the application does not fabricate metrics.

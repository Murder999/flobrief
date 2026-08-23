# PostPiloter — Codex Development Guide

## Product
PostPiloter is a premium B2B SaaS platform for agency-brand brief management, approval workflows, content calendar, reporting, white-label, and subscription management.

## 15-Part Development Rules (HISTORICAL — not current working method)
- Read only project memory files at part start — never read old chat PDFs
- No mock services in production module code (mock data only in demo seed files)
- No placeholder components, no TODO/FIXME comments in committed code
- No half-finished implementations — every file ships production-quality logic
- Every part ends with: `ruff + pytest` (backend), `typecheck + build` (frontend)
- Fix all errors before marking a part complete
- Update `PROJECT_STATE.md` (max 220 lines, compress not expand) and `TODO_NEXT.md` after every part
- Update `docs/DECISIONS.md` with technical decisions made in each part

**Note**: The historical 15-part plan is not the current working method. Production readiness is governed by `docs/LAUNCH_CHECKLIST.md`, `PROJECT_STATE.md`, and `TODO_NEXT.md`. Do not treat the historical plan as active development guidance.

## Architecture Rules
- Multi-tenant from day one: every DB query scoped to `agency_id`
- Three user tiers: `platform_admin` (tenant-independent) › `agency_*` roles › `brand_*` roles
- `platform_admin` hiçbir agency/brand'e üye olamaz; JWT'de `agency_id` yoktur; yalnızca `/api/v1/platform/` erişir
- `platform_admin` sadece secure bootstrap CLI scriptiyle oluşturulur — kayıt/davet akışı yoktur
- RBAC: all endpoints check role before executing
- Tenant audit log: tenant-scoped `activity_logs`; Platform audit log: immutable `platform_audit_logs`
- JWT auth with refresh token rotation; platform_admin token ömrü tenant token'dan daha kısadır
- Pydantic settings — no hardcoded config values
- SQLAlchemy async sessions only
- Alembic for all schema migrations — never alter DB directly

## UI/UX Rules (Frontend — Premium SaaS Quality)
- UI must feel like a finished premium SaaS product, not AI-generated card clutter
- Prefer strong information architecture over adding more cards
- Avoid unnecessary vertical page length
- Desktop should feel premium; mobile must remain fully usable
- Every feature must preserve meaningful loading, empty and error states where relevant
- Do not add decorative complexity without product value
- Existing PostPiloter design language should be reused before inventing new visual systems
- PostPiloter has separate Agency and Brand portal experiences
- Never weaken tenant isolation, RBAC, authorization, or portal separation for UI convenience
- Agency and Brand portal behavior may share reusable components, but role-specific permissions and data boundaries must remain explicit
- Never invent backend capabilities solely to satisfy a frontend design
- Existing API contracts and real capabilities must be inspected before adding UI controls

## Token Efficiency
- Start each part by reading: `AGENTS.md`, `PROJECT_STATE.md`, `TODO_NEXT.md`, `PART_PLAN.md`
- Read only files that will be modified in that part
- Do not re-read unchanged files

## Stack
- **Backend**: Python, FastAPI, PostgreSQL, SQLAlchemy async, Alembic, Pydantic Settings, JWT, Pytest, Ruff
- **Frontend**: Next.js, TypeScript, Tailwind CSS, premium component system
- **Infra**: Docker Compose, PostgreSQL, Redis, MailHog, Makefile

## Part Plan Summary
See `PART_PLAN.md` for full 15-part plan. Current state is tracked in `PROJECT_STATE.md` and `TODO_NEXT.md`.

## Commands (Makefile — Windows PowerShell Friendly)
Windows PowerShell'de `&&` kullanmayın. Komutları ayrı tool çağrıları olarak çalıştırın.

- `make up` — Start PostgreSQL, Redis, MailHog (Compose); `docker compose up -d`
- `make down` — Stop all services; `docker compose down`
- `make backend-install` — `cd apps/backend && pip install -e ".[dev]"`
- `make backend-dev` — `cd apps/backend && python scripts/predev_check.py && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
  - PowerShell'de bu iki komutu birleştirebilirsiniz: `python scripts/predev_check.py; uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- `make backend-lint` — `cd apps/backend && ruff check . && ruff format --check .`
  - PowerShell'te her komut ayrı çağrılmalı: `ruff check .` ardından `ruff format --check .`
- `make backend-test` — `cd apps/backend && pytest -v --tb=short`
- `make frontend-install` — `cd apps/frontend && npm install`
- `make frontend-dev` — `cd apps/frontend && npm run dev`
- `make frontend-build` — `cd apps/frontend && npm run build`
- `make frontend-typecheck` — `cd apps/frontend && npm run typecheck`
- `make migrate` — `cd apps/backend && alembic upgrade head`
- `make migrate-create MSG='desc'` — `cd apps/backend && alembic revision --autogenerate -m "$(MSG)"`
- `make db-reset` — Drop & recreate DB (dev only)
- `make seed` — `cd apps/backend && python scripts/seed_plans.py`
- `make seed-demo` — `cd apps/backend && python scripts/seed_demo.py`
- `make create-platform-admin` — `cd apps/backend && python scripts/create_platform_admin.py`

**PowerShell not**: `tail`, `grep`, `sed`, `awk` gibi Unix araçlarının Windows'ta kurulu olmayabilir. Komutlar `Select-String` (grep alternative), `Get-Content` (cat alternative) olarak çalıştırılmalı. `&&` ile chaining yapmaktan kaçının; her komutu ayrı satır olarak çalıştırın.

## Environment (3 surfaces)
- Root `.env`: Docker Compose interpolation (`POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`). Never commit populated `.env`.
- `apps/backend/.env.prod`: FastAPI runtime settings. Sanitised examples version-controlled; populated files in `.gitignore`.
- `apps/frontend/.env.local`: Next.js build/runtime. `NEXT_PUBLIC_*` compiled into browser bundle — must be present at build time. Changing only running container env does NOT rewrite built bundle.

## CORS & Origins
- `CORS_ORIGINS` must include frontend origin. In production, set to `https://postpiloter.com`.
- `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` are Docker build args in `docker-compose.prod.yml`; change only via rebuild.
- `FRONTEND_URL` and `FRONTEND_PUBLIC_URL` in `apps/backend/.env.prod` drive email/action links.

## Platform Admin
- `platform_admin` is tenant-independent, has no `agency_id` claim, and is restricted to `/api/v1/platform/` namespace.
- Only creation method: `make create-platform-admin` (secure bootstrap CLI script).
- `platform_admin` token expiry: 5 min access / 8 hr refresh (configure via `PLATFORM_ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES`, `PLATFORM_ADMIN_REFRESH_TOKEN_EXPIRE_HOURS`).
- `PLATFORM_ADMIN_IP_ALLOWLIST` — comma-separated IP/CIDR; set only after confirming stable trusted source IP.
- `PLATFORM_ADMIN_MFA_RATE_LIMIT` — configure TOTP MFA enrollment before enabling.

## Demo Sandbox
- `DEMO_SANDBOX_TURNSTILE_SITE_KEY` and `DEMO_SANDBOX_TURNSTILE_SECRET_KEY` must be configured in `apps/backend/.env.prod` to enable public demo.
- `/platform/demo` as platform admin controls duration, capacity, per-IP quota, CAPTCHA policy.
- Demo tenants have fixed expiry, auto-suspend, and block external email/WhatsApp, invitations, billing, payments, invoice sending, and accounting connections.
- `/demo` creates unique, time-limited agency with seeded data; external delivery suppressed.

## PostPiloter Portal Rules
- PostPiloter has separate Agency and Brand portal experiences.
- Never weaken tenant isolation, RBAC, authorization, or portal separation for UI convenience.
- Agency and Brand portal behavior may share reusable components, but role-specific permissions and data boundaries must remain explicit.
- Never invent backend capabilities solely to satisfy a frontend design.
- Existing API contracts and real capabilities must be inspected before adding UI controls.

## TR / EN Kuralı
PostPiloter TR/EN çok dilli çalışır.

- New user-facing text must use the existing localization system.
- Do not hardcode new visible Turkish or English strings when an i18n path exists.
- Update both TR and EN translations for newly introduced product copy.
- Do not put portal/settings translations into unrelated marketing translation files.

## Git Güvenlik (Windows PowerShell Ortamı)
- Existing uncommitted changes must never be reverted or overwritten.
- Unrelated files must not be modified.
- Never run `git reset --hard`.
- Never run `git restore .`.
- Never run `git clean -fd`.
- Never run destructive checkout/stash/rebase operations.
- Do not commit unless the user explicitly requests it.
- Do not push unless the user explicitly requests it.
- Do not deploy or publish production unless the user explicitly requests it.
- Before changing an already-modified file, inspect the existing diff and preserve unrelated user work.

These rules are also enforced by `opencode.json` permission settings, but appear as behavioral guidance in AGENTS.md too.

## Model / Subagent Guidance
`opencode.json` içinde tanımlı ajanları gerektiğinde kullan:

- `build`: normal implementation and integration work.
- `deep-code`: difficult multi-file refactors, architecture, backend logic, authentication/authorization and difficult debugging.
- `ui-ux`: complex frontend architecture, responsive UI, design-system and premium UX work.
- `security-review`: read-only security review for auth, RBAC, tenant isolation, API exposure, validation, secrets and security-sensitive changes.

Ana agent gerektiğinde uygun subagent'tan yardım alabilir, ancak gereksiz yere her görevde tüm subagent'ları çağırmasın.

## Test / Verification (Windows-Adapted)
Full test suite yaklaşık 1777 test içeriyor ve uzun sürebiliyor.

- Küçük değişiklik sırasında önce focused test/typecheck/lint çalıştır.
- İş tamamlanırken gereken kapsamda daha geniş verification yap.
- Test timeout'u test failure olarak raporla.
- Pre-existing formatting/test sorunları yeni değişikliklerin hatası gibi raporlama.
- Mevcut olarak şu dosyalar önceden formatlama gerektiriyor (AGENTS.md güncellemesi için değiştirilmedi):
  - `alembic/versions/s4t5u6v7w8x9_complete_white_label_branding.py`
  - `app/api/v1/auth.py`
  - `app/services/notification_dispatcher.py`
  - `app/tests/test_resend_production_flows.py`
- `tail`, `grep` gibi araçlar Windows'ta `Select-String` olarak çalıştırılmalı.
- Komutlar `&&` ile chaining yapılarak değil, ayrı satırlar olarak çalıştırılmalı.

## Verification Order (Windows PowerShell)
- `ruff check .` → `ruff format --check .` → `pytest -v --tb=short` (focused) → `npm run typecheck` → `npm run build`
- Full test suite timeout'landırabilir; adım adım focused verification tercih edilmelidir.

## Production Readiness
- Release governed by `docs/LAUNCH_CHECKLIST.md`, not by historical 15-part plan completion.
- Green push to `main` can deploy to Hetzner via guarded `deploy_hetzner` CI job (requires `HETZNER_DEPLOY_ENABLED=true`).
- Before deploy: `ruff check`, focused `pytest`, `npm ci && npm run typecheck && npm run build`.
- Hetzner deployment: backups, migration head check, commit-tagged images, health verify, rollback on failure.
- Local media storage on `media_data` volume; off-host backups mandatory.

## Agent Workflow
- For implementation tasks, begin real repository/tool inspection promptly.
- Do not spend extended periods only describing plans.
- Break large scopes into verifiable implementation phases.
- Finish and verify one coherent phase before moving to another.
- Do not mark a task complete merely because a reusable component was created; it must actually be integrated.
- Prefer focused verification while developing instead of repeatedly running the entire test suite.
- If a command/tool hangs or times out, diagnose it and use a narrower alternative rather than repeatedly retrying the same approach.

## Sadece AGENTS.md dosyası güncellendi. Değişiklikler:

### Eski/stale kurallar kaldırıldı:
- "Flobrief" ürün ismi → "PostPiloter" olarak güncellendi
- Genel "Linux/macOS shell varsayma" önerisi → Windows PowerShell kuraları ile değiştirildi
- "&&" kullanımı kabul görme
- `tail`, `grep`, `sed` gibi Unix araçlarının hazır olarak bulunduğu varsayımı
- Tarihsel 15-part planın aktif working method olduğu örneği

### Yeni repo kuralları eklendi:
- Windows PowerShell ortamı kuralları ( `&&` kullanımı, Unix araçları, `tail` alternatifi)
- Git güvenliği kuralları (uncommitted changes preservation, destructive ops yasası)
- PostPiloter portal kuralları (Agency/Brand ayrımı, RBAC/zayıfleştirme yasası)
- TR/EN çok dilli kuralar
- UI/UX premium kalite kırılarak yeniden düzenlenmiş kurallar
- Agent çalışmaAkışı ve subagent yönlendirme kılavuzu
- Test verification Windows uyumlu uyarlaması
- Pre-existing formatting issue farkı belirtme (AGENTS.md için değiştirilmedi)
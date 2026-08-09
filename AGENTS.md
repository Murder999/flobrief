# Flobrief — Codex Development Guide

## Project
Flobrief is a premium B2B SaaS platform for agencies and brands: brief management, approval/revision workflows, content calendar, reporting, white-label, notifications, and subscription management.

## 15-Part Development Rules

### Core Rules (Every Part)
- Read only project memory files at part start — never read old chat PDFs
- No mock services in production module code (mock data only in demo seed files)
- No placeholder components, no TODO/FIXME comments in committed code
- No half-finished implementations — every file ships production-quality logic
- Every part ends with: ruff + pytest (backend), typecheck + build (frontend)
- Fix all errors before marking a part complete
- Update PROJECT_STATE.md (max 220 lines, compress not expand) and TODO_NEXT.md after every part
- Update docs/DECISIONS.md with technical decisions made in each part

### Architecture Rules
- Multi-tenant from day one: every DB query scoped to agency_id
- Three user tiers: `platform_admin` (tenant-independent) › `agency_*` roles › `brand_*` roles
- `platform_admin` hiçbir agency/brand'e üye olamaz; JWT'de agency_id yoktur; yalnızca `/api/v1/platform/` erişir
- `platform_admin` sadece secure bootstrap CLI scriptiyle oluşturulur — kayıt/davet akışı yoktur
- RBAC: all endpoints check role before executing
- Tenant audit log: tenant-scoped `activity_logs`; Platform audit log: immutable `platform_audit_logs`
- JWT auth with refresh token rotation; platform_admin token ömrü tenant token'dan daha kısadır
- Pydantic settings — no hardcoded config values
- SQLAlchemy async sessions only
- Alembic for all schema migrations — never alter DB directly

### UI/UX Rules (Frontend)
- Premium SaaS quality: Linear / Attio / Stripe Dashboard / Vercel feel
- Never a plain gray admin panel
- Every screen: loading skeleton + empty state + error state
- Ferah spacing, strong typography, soft shadows, clear hierarchy
- Brand approval portal must be visually presentable to agency clients
- Content calendar is the showcase screen
- Dashboard must work as a sales demo
- Responsive design mandatory
- Weak visual quality = part not complete

### Token Efficiency
- Start each part by reading: AGENTS.md, PROJECT_STATE.md, TODO_NEXT.md, PART_PLAN.md
- Read only files that will be modified in that part
- Do not re-read unchanged files

## Stack
- **Backend**: Python, FastAPI, PostgreSQL, SQLAlchemy async, Alembic, Pydantic Settings, JWT, Pytest, Ruff
- **Frontend**: Next.js, TypeScript, Tailwind CSS, premium component system
- **Infra**: Docker Compose, PostgreSQL, Redis, MailHog, Makefile

## Part Plan Summary
See PART_PLAN.md for full 15-part plan.

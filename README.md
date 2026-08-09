# Flobrief

Premium B2B SaaS platform for agency-brand brief management, approval workflows, content calendar, reporting, white-label, and subscription management.

## Stack

- **Backend**: Python 3.11+, FastAPI, PostgreSQL 16, SQLAlchemy 2.x async, Alembic, Pydantic Settings, JWT
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS
- **Infra**: Docker Compose, PostgreSQL, Redis, MailHog

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose

### Start Infrastructure
```bash
make up
```

### Backend
```bash
make backend-install
make backend-dev
# API: http://localhost:8000
# Docs: http://localhost:8000/api/docs
```

### Frontend
```bash
make frontend-install
make frontend-dev
# App: http://localhost:3000
```

### Database Migrations
```bash
make migrate
```

## Development

```bash
make backend-lint     # Ruff lint + format check
make backend-test     # pytest
make frontend-typecheck  # TypeScript check
make frontend-build   # Production build
```

## Project Structure

```
apps/
  backend/    FastAPI API server
  frontend/   Next.js web app
packages/
  shared/     Shared types (future)
docs/         Architecture, DB schema, UI DNA, Security rules
infra/        Nginx configs (production)
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Database Schema](docs/DATABASE.md)
- [UI/UX Design System](docs/UI_DNA.md)
- [Security Rules](docs/SECURITY_RULES.md)
- [Technical Decisions](docs/DECISIONS.md)
- [15-Part Development Plan](PART_PLAN.md)

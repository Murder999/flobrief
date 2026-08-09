.PHONY: help up down backend-install backend-dev backend-lint backend-test \
        frontend-install frontend-dev frontend-build frontend-typecheck \
        migrate migrate-create db-reset seed seed-demo \
        docker-build docker-up create-platform-admin

BACKEND_DIR = apps/backend
FRONTEND_DIR = apps/frontend

help:
	@echo "Flobrief Development Commands"
	@echo "============================="
	@echo "Infrastructure:"
	@echo "  make up                  Start PostgreSQL, Redis, MailHog"
	@echo "  make down                Stop all services"
	@echo "  make docker-build        Build production Docker images"
	@echo "  make docker-up           Start production Docker stack"
	@echo ""
	@echo "Backend:"
	@echo "  make backend-install     Install Python dependencies"
	@echo "  make backend-dev         Start FastAPI dev server"
	@echo "  make backend-lint        Run Ruff linter"
	@echo "  make backend-test        Run pytest"
	@echo ""
	@echo "Frontend:"
	@echo "  make frontend-install    Install npm dependencies"
	@echo "  make frontend-dev        Start Next.js dev server"
	@echo "  make frontend-build      Build for production"
	@echo "  make frontend-typecheck  TypeScript check"
	@echo ""
	@echo "Database:"
	@echo "  make migrate             Run Alembic migrations"
	@echo "  make migrate-create MSG='description'  Create new migration"
	@echo "  make db-reset            Drop & recreate DB (dev only)"
	@echo "  make seed                Run base seed (plans)"
	@echo "  make seed-demo           Run demo seed (agency + full data)"
	@echo ""
	@echo "Admin:"
	@echo "  make create-platform-admin   Bootstrap first platform admin"

up:
	docker compose up -d
	@echo "Services started. PostgreSQL: 5433 | Redis: 6379 | MailHog: 8025"

down:
	docker compose down

backend-install:
	cd $(BACKEND_DIR) && pip install -e ".[dev]"

backend-dev:
	cd $(BACKEND_DIR) && python scripts/predev_check.py && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-lint:
	cd $(BACKEND_DIR) && ruff check . && ruff format --check .

backend-test:
	cd $(BACKEND_DIR) && pytest -v --tb=short

frontend-install:
	cd $(FRONTEND_DIR) && npm install

frontend-dev:
	cd $(FRONTEND_DIR) && npm run dev

frontend-build:
	cd $(FRONTEND_DIR) && npm run build

frontend-typecheck:
	cd $(FRONTEND_DIR) && npm run typecheck

migrate:
	cd $(BACKEND_DIR) && alembic upgrade head

migrate-create:
	cd $(BACKEND_DIR) && alembic revision --autogenerate -m "$(MSG)"

db-reset:
	@echo "WARNING: This will drop and recreate the database!"
	docker compose exec postgres psql -U flobrief -c "DROP DATABASE IF EXISTS flobrief;"
	docker compose exec postgres psql -U flobrief -c "CREATE DATABASE flobrief;"
	$(MAKE) migrate

seed:
	cd $(BACKEND_DIR) && python scripts/seed_plans.py

seed-demo:
	cd $(BACKEND_DIR) && python scripts/seed_demo.py

docker-build:
	docker compose -f docker-compose.prod.yml build

docker-up:
	docker compose -f docker-compose.prod.yml up -d

create-platform-admin:
	cd $(BACKEND_DIR) && python scripts/create_platform_admin.py

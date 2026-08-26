#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${1:-}"
RELEASE_SHA="${2:-}"
PRODUCTION_URL="${3:-}"
COMPOSE_FILE="docker-compose.prod.yml"
PADDLE_ENV_FILE=".env.paddle"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-flobrief}"
BACKUP_DIR=""
PREVIOUS_SHA=""
APPLICATION_SWITCH_STARTED=false

log() {
  printf '[deploy] %s\n' "$*"
}

fail() {
  printf '[deploy] ERROR: %s\n' "$*" >&2
  return 1
}

if [[ ! "$APP_DIR" =~ ^/[A-Za-z0-9._/-]+$ || "$APP_DIR" == "/" ]]; then
  fail "APP_DIR must be a safe absolute path"
fi

if [[ ! "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  fail "RELEASE_SHA must be a full Git commit SHA"
fi

if [[ ! "$PRODUCTION_URL" =~ ^https://[A-Za-z0-9.-]+(:[0-9]{1,5})?/?$ ]]; then
  fail "PRODUCTION_URL must be an HTTPS origin"
fi

[[ -d "$APP_DIR/.git" ]] || fail "$APP_DIR is not a Git checkout"
cd "$APP_DIR"

[[ -f "$COMPOSE_FILE" ]] || fail "$COMPOSE_FILE is missing"
[[ -f .env ]] || fail "$APP_DIR/.env is missing"
[[ -f "$PADDLE_ENV_FILE" ]] || fail "$APP_DIR/$PADDLE_ENV_FILE is missing"
[[ -f apps/backend/.env.prod ]] || fail "apps/backend/.env.prod is missing"
[[ -s infra/nginx/certs/fullchain.pem ]] || fail "TLS fullchain.pem is missing"
[[ -s infra/nginx/certs/privkey.pem ]] || fail "TLS privkey.pem is missing"

command -v git >/dev/null || fail "git is not installed"
command -v docker >/dev/null || fail "Docker is not installed"
command -v curl >/dev/null || fail "curl is not installed"
command -v flock >/dev/null || fail "flock is not installed"
command -v gzip >/dev/null || fail "gzip is not installed"
command -v sha256sum >/dev/null || fail "sha256sum is not installed"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is not installed"

exec 9>/tmp/flobrief-production-deploy.lock
flock -n 9 || fail "another Flobrief deployment is already running"

if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
  fail "server checkout has uncommitted or untracked files"
fi

case "$(git remote get-url origin)" in
  https://github.com/Murder999/flobrief.git|git@github.com:Murder999/flobrief.git)
    ;;
  *)
    fail "origin does not point to Murder999/flobrief"
    ;;
esac

PREVIOUS_SHA="$(git rev-parse HEAD)"
BACKUP_DIR="$APP_DIR/backups/$(date -u +%Y%m%dT%H%M%SZ)-$PREVIOUS_SHA"

compose() {
  COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" RELEASE_SHA="$1" \
    docker compose --env-file .env --env-file "$PADDLE_ENV_FILE" -f "$COMPOSE_FILE" "${@:2}"
}

container_is_running() {
  local service="$1"
  local container_id
  container_id="$(compose "$PREVIOUS_SHA" ps -q "$service" 2>/dev/null || true)"
  [[ -n "$container_id" && "$(docker inspect --format '{{.State.Running}}' "$container_id" 2>/dev/null)" == "true" ]]
}

tag_previous_image() {
  local service="$1"
  local target="$2"
  local container_id image_id
  container_id="$(compose "$PREVIOUS_SHA" ps -q "$service" 2>/dev/null || true)"
  [[ -n "$container_id" ]] || return 0
  image_id="$(docker inspect --format '{{.Image}}' "$container_id")"
  docker image tag "$image_id" "$target:$PREVIOUS_SHA"
}

backup_persistent_data() {
  if ! container_is_running postgres; then
    log "PostgreSQL is not running; treating this as an initial deployment without a database backup"
    return 0
  fi

  install -d -m 700 "$BACKUP_DIR"
  log "Creating pre-deploy PostgreSQL backup"
  compose "$PREVIOUS_SHA" exec -T postgres \
    sh -ec 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
    | gzip -9 > "$BACKUP_DIR/postgres.sql.gz"
  test -s "$BACKUP_DIR/postgres.sql.gz" || fail "PostgreSQL backup is empty"

  if container_is_running backend; then
    log "Creating pre-deploy media backup"
    compose "$PREVIOUS_SHA" exec -T backend \
      tar -C /app -czf - media > "$BACKUP_DIR/media.tar.gz"
    test -s "$BACKUP_DIR/media.tar.gz" || fail "media backup is empty"
  fi

  sha256sum "$BACKUP_DIR"/*.gz > "$BACKUP_DIR/SHA256SUMS"
  log "Backups written to $BACKUP_DIR; off-host backup policy remains mandatory"
}

service_ready() {
  local release="$1"
  local service="$2"
  local container_id state health
  container_id="$(compose "$release" ps -q "$service" 2>/dev/null || true)"
  [[ -n "$container_id" ]] || return 1
  state="$(docker inspect --format '{{.State.Status}}' "$container_id")"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")"
  [[ "$state" == "running" && ( "$health" == "healthy" || "$health" == "none" ) ]]
}

wait_for_stack() {
  local release="$1"
  local deadline=$((SECONDS + 240))
  local service
  while (( SECONDS < deadline )); do
    for service in postgres redis backend frontend nginx; do
      service_ready "$release" "$service" || break
    done
    if [[ "$service" == "nginx" ]] && service_ready "$release" nginx; then
      return 0
    fi
    sleep 5
  done
  return 1
}

rollback_application() {
  [[ "$APPLICATION_SWITCH_STARTED" == "true" ]] || return 0
  [[ -n "$PREVIOUS_SHA" ]] || return 0

  log "Deployment failed; restoring the previous application images"
  git checkout --detach "$PREVIOUS_SHA" >/dev/null 2>&1 || true
  COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" RELEASE_SHA="$PREVIOUS_SHA" \
    docker compose --env-file .env --env-file "$PADDLE_ENV_FILE" -f "$COMPOSE_FILE" \
      up -d --no-build --no-deps backend frontend nginx || true
  log "Application rollback attempted. Database changes were not downgraded automatically."
}

on_error() {
  local exit_code=$?
  set +e
  log "Deployment command failed with exit code $exit_code"
  COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" RELEASE_SHA="$RELEASE_SHA" \
    docker compose --env-file .env --env-file "$PADDLE_ENV_FILE" -f "$COMPOSE_FILE" ps
  COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" RELEASE_SHA="$RELEASE_SHA" \
    docker compose --env-file .env --env-file "$PADDLE_ENV_FILE" -f "$COMPOSE_FILE" \
      logs --tail=150 backend frontend nginx
  rollback_application
  exit "$exit_code"
}
trap on_error ERR

backup_persistent_data
tag_previous_image backend flobrief-backend
tag_previous_image frontend flobrief-frontend

log "Fetching the verified main-branch commit"
git fetch --prune origin main
git cat-file -e "$RELEASE_SHA^{commit}" || fail "release commit is not available from origin"
[[ "$(git rev-parse "$RELEASE_SHA^{commit}")" == "$RELEASE_SHA" ]] || fail "release SHA did not resolve exactly"
git merge-base --is-ancestor "$RELEASE_SHA" origin/main || fail "release commit is not part of origin/main"
git checkout --detach "$RELEASE_SHA"

log "Building release images"
compose "$RELEASE_SHA" build --pull backend frontend

log "Starting PostgreSQL and Redis"
compose "$RELEASE_SHA" up -d postgres redis

log "Checking Alembic migration graph"
heads_output="$(compose "$RELEASE_SHA" run --rm backend alembic heads)"
head_count="$(grep -c '(head)' <<<"$heads_output" || true)"
[[ "$head_count" == "1" ]] || fail "Alembic must report exactly one head"

log "Applying database migrations and idempotent plan seed"
compose "$RELEASE_SHA" run --rm backend alembic upgrade head
compose "$RELEASE_SHA" run --rm backend python scripts/seed_plans.py

log "Switching application services to $RELEASE_SHA"
APPLICATION_SWITCH_STARTED=true
compose "$RELEASE_SHA" up -d --no-build --remove-orphans backend frontend nginx

wait_for_stack "$RELEASE_SHA" || fail "containers did not become healthy within 240 seconds"

base_url="${PRODUCTION_URL%/}"
log "Verifying public frontend and API health"
curl --fail --silent --show-error --retry 10 --retry-delay 3 --retry-all-errors \
  --max-time 20 "$base_url/api/v1/health" >/dev/null
curl --fail --silent --show-error --retry 10 --retry-delay 3 --retry-all-errors \
  --max-time 20 "$base_url/" >/dev/null

install -d -m 700 "$APP_DIR/.deploy"
printf '%s\n' "$RELEASE_SHA" > "$APP_DIR/.deploy/current-release"
trap - ERR
log "Deployment completed successfully: $RELEASE_SHA"

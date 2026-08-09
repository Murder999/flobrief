FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

FROM base AS builder
# gcc/libpq-dev: asyncpg/SQLAlchemy; libjpeg-dev/zlib1g-dev: Pillow; mupdf-dev: PyMuPDF fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libjpeg-dev zlib1g-dev libffi-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM base AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl libjpeg62-turbo libgles2 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
RUN useradd --no-create-home --uid 1001 appuser
COPY . .
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

COPY start.sh /app/start.sh
CMD ["/bin/sh", "/app/start.sh"]

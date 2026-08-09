import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import FlobriefError

_INLINE_XSS_CAPABLE_MEDIA_TYPES = frozenset(
    {
        "image/svg+xml",
        "text/html",
        "application/xhtml+xml",
    }
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        response: Response = await call_next(request)  # type: ignore[operator]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/media/"):
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type in _INLINE_XSS_CAPABLE_MEDIA_TYPES:
                # Uploads are MIME-allowlisted at write time (SVG/HTML are
                # rejected there), so this only fires for legacy/unexpected
                # files already on disk — defense in depth, not the primary
                # control. Scoped to SVG/HTML specifically: applying this to
                # every /media/ response (images, video, PDFs) would force
                # browsers to download instead of preview them inline,
                # breaking the product's core media-preview UX for no
                # security benefit, since those types can't execute script.
                response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
                response.headers["Content-Disposition"] = "attachment"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from app.services.deadline_scheduler import start_deadline_scheduler
    from app.services.demo_sandbox_scheduler import start_demo_sandbox_scheduler
    from app.services.finance_capacity_scheduler import start_finance_capacity_scheduler
    from app.services.notification_realtime import start_notification_realtime_broker
    from app.services.time_tracking_scheduler import start_time_tracking_scheduler
    from app.services.whatsapp_retry_worker import start_whatsapp_retry_worker

    task = start_deadline_scheduler()
    demo_sandbox_task = start_demo_sandbox_scheduler()
    time_tracking_task = start_time_tracking_scheduler()
    finance_capacity_task = start_finance_capacity_scheduler()
    notification_realtime_task = start_notification_realtime_broker()
    whatsapp_retry_task = start_whatsapp_retry_worker()
    try:
        yield
    finally:
        task.cancel()
        demo_sandbox_task.cancel()
        time_tracking_task.cancel()
        finance_capacity_task.cancel()
        notification_realtime_task.cancel()
        whatsapp_retry_task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await task
        with suppress(asyncio.CancelledError, Exception):
            await demo_sandbox_task
        with suppress(asyncio.CancelledError, Exception):
            await time_tracking_task
        with suppress(asyncio.CancelledError, Exception):
            await finance_capacity_task
        with suppress(asyncio.CancelledError, Exception):
            await notification_realtime_task
        with suppress(asyncio.CancelledError, Exception):
            await whatsapp_retry_task


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        docs_url="/api/docs" if settings.APP_DEBUG else None,
        redoc_url="/api/redoc" if settings.APP_DEBUG else None,
        openapi_url="/api/openapi.json" if settings.APP_DEBUG else None,
        lifespan=lifespan,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins(),
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Agency-ID", "X-Impersonation-Token"],
    )

    app.include_router(api_router, prefix="/api/v1")

    # Serve uploaded media files (logos, assets) at /media
    media_root = settings.MEDIA_ROOT
    os.makedirs(media_root, exist_ok=True)
    app.mount("/media", StaticFiles(directory=media_root), name="media")

    @app.get("/health", tags=["health"], include_in_schema=False)
    async def root_health() -> dict[str, str]:
        return {"status": "ok", "service": "flobrief-api"}

    @app.exception_handler(FlobriefError)
    async def flobrief_error_handler(request: Request, exc: FlobriefError) -> JSONResponse:
        status_map = {
            "not_found": 404,
            "permission_denied": 403,
            "conflict": 409,
            "validation_error": 422,
            "internal_error": 500,
        }
        status_code = status_map.get(exc.code, 500)
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    return app


app = create_application()

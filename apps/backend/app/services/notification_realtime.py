"""Redis-backed, tenant-scoped real-time notification transport."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Literal

from fastapi import WebSocket
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limiter import get_redis_client

logger = logging.getLogger(__name__)

_CHANNEL = "flobrief:realtime:notifications"
_TICKET_PREFIX = "flobrief:realtime:ticket:"
_PENDING_KEY = "flobrief_realtime_notification_signals"


class RealtimeUnavailableError(RuntimeError):
    """Raised when Redis cannot safely issue or consume a connection ticket."""


@dataclass(frozen=True)
class NotificationConnectionClaims:
    user_id: str
    portal: Literal["agency", "brand"]
    agency_id: str | None = None
    brand_id: str | None = None


def _ticket_key(ticket: str) -> str:
    digest = hashlib.sha256(ticket.encode("utf-8")).hexdigest()
    return f"{_TICKET_PREFIX}{digest}"


async def issue_ticket(claims: NotificationConnectionClaims) -> str:
    ticket = secrets.token_urlsafe(32)
    try:
        stored = await get_redis_client().set(
            _ticket_key(ticket),
            json.dumps(asdict(claims), separators=(",", ":")),
            ex=settings.NOTIFICATION_WS_TICKET_TTL_SECONDS,
            nx=True,
        )
    except Exception as exc:
        logger.warning("Real-time notification ticket could not be issued: %s", exc)
        raise RealtimeUnavailableError from exc
    if not stored:
        raise RealtimeUnavailableError("Redis rejected the connection ticket")
    return ticket


async def consume_ticket(ticket: str) -> NotificationConnectionClaims | None:
    if not ticket or len(ticket) > 256:
        return None
    try:
        raw = await get_redis_client().getdel(_ticket_key(ticket))
    except Exception as exc:
        logger.warning("Real-time notification ticket could not be consumed: %s", exc)
        raise RealtimeUnavailableError from exc
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        portal = payload["portal"]
        if portal not in ("agency", "brand"):
            raise ValueError("Invalid portal")
        agency_id = str(uuid.UUID(payload["agency_id"])) if payload.get("agency_id") else None
        brand_id = str(uuid.UUID(payload["brand_id"])) if payload.get("brand_id") else None
        if (portal == "agency" and agency_id is None) or (portal == "brand" and brand_id is None):
            raise ValueError("Missing tenant scope")
        return NotificationConnectionClaims(
            user_id=str(uuid.UUID(payload["user_id"])),
            portal=portal,
            agency_id=agency_id,
            brand_id=brand_id,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Discarded malformed real-time notification ticket")
        return None


def queue_notification_signal(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    agency_id: uuid.UUID | None,
    brand_id: uuid.UUID | None,
) -> None:
    """Queue a signal on the current transaction; publish only after commit."""
    signals: dict[tuple[str, str | None, str | None], dict[str, str | None]] = db.info.setdefault(
        _PENDING_KEY, {}
    )
    key = (
        str(user_id),
        str(agency_id) if agency_id else None,
        str(brand_id) if brand_id else None,
    )
    signals[key] = {
        "type": "notifications.changed",
        "user_id": key[0],
        "agency_id": key[1],
        "brand_id": key[2],
    }


async def _publish_signals(signals: list[dict[str, str | None]]) -> None:
    try:
        client = get_redis_client()
        for signal in signals:
            await client.publish(_CHANNEL, json.dumps(signal, separators=(",", ":")))
    except Exception as exc:
        # WebSocket delivery is ephemeral. The frontend polling fallback repairs
        # any missed signal without affecting the committed product action.
        logger.warning("Real-time notification signal could not be published: %s", exc)


@event.listens_for(Session, "after_commit")
def _publish_after_commit(session: Session) -> None:
    pending = session.info.pop(_PENDING_KEY, None)
    if not pending:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("No event loop available for real-time notification publish")
        return
    loop.create_task(_publish_signals(list(pending.values())))


@event.listens_for(Session, "after_rollback")
def _discard_after_rollback(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)


class NotificationConnectionHub:
    def __init__(self) -> None:
        self._connections: dict[WebSocket, NotificationConnectionClaims] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, claims: NotificationConnectionClaims) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = claims

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.pop(websocket, None)

    @staticmethod
    def _matches(claims: NotificationConnectionClaims, signal: dict[str, Any]) -> bool:
        if signal.get("user_id") != claims.user_id:
            return False
        if claims.portal == "agency":
            return bool(claims.agency_id and signal.get("agency_id") == claims.agency_id)
        return bool(claims.brand_id and signal.get("brand_id") == claims.brand_id)

    async def dispatch(self, signal: dict[str, Any]) -> None:
        async with self._lock:
            targets = [
                websocket
                for websocket, claims in self._connections.items()
                if self._matches(claims, signal)
            ]
        failed: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json({"type": "notifications.changed"})
            except Exception:
                failed.append(websocket)
        for websocket in failed:
            await self.disconnect(websocket)


notification_connection_hub = NotificationConnectionHub()


def is_allowed_websocket_origin(origin: str | None) -> bool:
    if origin is None:
        return True
    allowed = {value.rstrip("/") for value in settings.get_cors_origins()}
    return "*" in allowed or origin.rstrip("/") in allowed


async def run_notification_realtime_broker() -> None:
    """Fan Redis pub/sub messages into this worker's local WebSockets."""
    while True:
        pubsub = None
        try:
            pubsub = get_redis_client().pubsub()
            await pubsub.subscribe(_CHANNEL)
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    signal = json.loads(message["data"])
                except (TypeError, json.JSONDecodeError):
                    logger.warning("Discarded malformed real-time notification signal")
                    continue
                if isinstance(signal, dict):
                    await notification_connection_hub.dispatch(signal)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Real-time notification broker disconnected: %s", exc)
            await asyncio.sleep(settings.NOTIFICATION_WS_RECONNECT_DELAY_SECONDS)
        finally:
            if pubsub is not None:
                await pubsub.aclose()


def start_notification_realtime_broker() -> asyncio.Task[None]:
    return asyncio.create_task(
        run_notification_realtime_broker(),
        name="notification-realtime-broker",
    )

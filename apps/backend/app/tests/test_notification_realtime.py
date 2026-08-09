from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import Session

from app.services import notification_realtime
from app.services.notification_realtime import (
    NotificationConnectionClaims,
    NotificationConnectionHub,
    consume_ticket,
    issue_ticket,
    queue_notification_signal,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, *, ex: int, nx: bool) -> bool:
        assert ex > 0
        assert nx is True
        if key in self.values:
            return False
        self.values[key] = value
        return True

    async def getdel(self, key: str) -> str | None:
        return self.values.pop(key, None)


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.messages: list[dict[str, str]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict[str, str]) -> None:
        self.messages.append(payload)


@pytest.mark.asyncio
async def test_realtime_ticket_is_single_use_and_preserves_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = FakeRedis()
    monkeypatch.setattr(notification_realtime, "get_redis_client", lambda: redis)
    user_id = uuid.uuid4()
    agency_id = uuid.uuid4()

    ticket = await issue_ticket(
        NotificationConnectionClaims(
            user_id=str(user_id),
            portal="agency",
            agency_id=str(agency_id),
        )
    )

    claims = await consume_ticket(ticket)
    assert claims == NotificationConnectionClaims(
        user_id=str(user_id),
        portal="agency",
        agency_id=str(agency_id),
    )
    assert await consume_ticket(ticket) is None
    assert ticket not in json.dumps(redis.values)


@pytest.mark.asyncio
async def test_connection_hub_enforces_user_and_tenant_scope() -> None:
    hub = NotificationConnectionHub()
    user_id = str(uuid.uuid4())
    agency_a = str(uuid.uuid4())
    agency_b = str(uuid.uuid4())
    socket_a = FakeWebSocket()
    socket_b = FakeWebSocket()

    await hub.connect(
        cast(Any, socket_a),
        NotificationConnectionClaims(
            user_id=user_id,
            portal="agency",
            agency_id=agency_a,
        ),
    )
    await hub.connect(
        cast(Any, socket_b),
        NotificationConnectionClaims(
            user_id=user_id,
            portal="agency",
            agency_id=agency_b,
        ),
    )
    await hub.dispatch(
        {
            "type": "notifications.changed",
            "user_id": user_id,
            "agency_id": agency_a,
            "brand_id": None,
        }
    )

    assert socket_a.accepted is True
    assert socket_a.messages == [{"type": "notifications.changed"}]
    assert socket_b.messages == []


@pytest.mark.asyncio
async def test_signal_publishes_only_after_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publish = AsyncMock()
    monkeypatch.setattr(notification_realtime, "_publish_signals", publish)
    session = Session()
    session.begin()

    queue_notification_signal(
        cast(Any, session),
        user_id=uuid.uuid4(),
        agency_id=uuid.uuid4(),
        brand_id=None,
    )
    assert publish.await_count == 0

    session.commit()
    await asyncio.sleep(0)
    assert publish.await_count == 1


@pytest.mark.asyncio
async def test_rollback_discards_queued_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publish = AsyncMock()
    monkeypatch.setattr(notification_realtime, "_publish_signals", publish)
    session = Session()
    session.begin()

    queue_notification_signal(
        cast(Any, session),
        user_id=uuid.uuid4(),
        agency_id=None,
        brand_id=uuid.uuid4(),
    )
    session.rollback()
    await asyncio.sleep(0)

    assert publish.await_count == 0
    assert "flobrief_realtime_notification_signals" not in session.info

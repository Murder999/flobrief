"""Live-database tests for annotation notification dispatch behavior:
no duplicate notifications per recipient, and provider/dispatch failures
must not abort the annotation operation while still being logged (not
silently swallowed).

Reuses the `tenants` fixture from conftest.py rather than duplicating
agency/brand/user/brief/deliverable/annotation setup.
"""

from __future__ import annotations

import logging

from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.notification import Notification, NotificationEvent
from app.services.notification_dispatcher import NotificationDispatcher
from app.tests.conftest import agency_headers


class TestNoDuplicateNotifications:
    async def test_annotation_create_dispatches_exactly_one_event_and_one_notification(
        self, client: AsyncClient, tenants
    ) -> None:
        tenant_a, _ = tenants
        resp = await client.post(
            f"/api/v1/briefs/{tenant_a.brief_id}/deliverables/{tenant_a.deliverable_id}/annotations",
            json={
                "body": "yeni revizyon",
                "x_percent": 10,
                "y_percent": 20,
                "visibility": "client_visible",
            },
            headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
        )
        assert resp.status_code == 201
        annotation_id = resp.json()["id"]

        async with AsyncSessionLocal() as session:
            events = (
                (
                    await session.execute(
                        select(NotificationEvent).where(
                            NotificationEvent.event_type == "annotation.created",
                            NotificationEvent.payload["annotation_id"].astext == annotation_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert (
                len(events) == 1
            ), "annotation create must dispatch exactly one event, not a duplicate"

            notifications = (
                (
                    await session.execute(
                        select(Notification).where(
                            Notification.event_id == events[0].id,
                            Notification.user_id == tenant_a.brand_manager_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert (
                len(notifications) == 1
            ), "the recipient must get exactly one in-app notification row"


class TestNotificationFailureDoesNotAbortOperation:
    async def test_dispatch_failure_does_not_abort_reply_and_is_logged(
        self, client: AsyncClient, tenants, monkeypatch, caplog
    ) -> None:
        tenant_a, _ = tenants

        async def _boom(self, brand_id):  # noqa: ARG001
            raise RuntimeError("simulated notification provider outage")

        monkeypatch.setattr(NotificationDispatcher, "get_brand_members", _boom)

        with caplog.at_level(logging.ERROR, logger="app.api.v1.deliverables"):
            resp = await client.post(
                f"/api/v1/annotations/{tenant_a.annotation_id}/replies"
                f"?deliverable_id={tenant_a.deliverable_id}",
                json={"body": "reply despite notification outage"},
                headers=agency_headers(tenant_a.agency_token, tenant_a.agency_id),
            )

        assert resp.status_code == 201, (
            "the reply itself must succeed per the fire-and-forget notification policy "
            "even though notification dispatch raised"
        )
        assert any(
            "annotation.replied" in record.message and record.levelno >= logging.ERROR
            for record in caplog.records
        ), "the notification dispatch failure must be logged, not silently swallowed"

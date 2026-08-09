"""Accounting connector endpoints (plan §9/§10): connector CRUD,
test-connection, and sync-invoice dispatch. Every mutating endpoint writes
an `ActivityLogRepository` row; `meta` never carries credential values or
decrypted secrets. `ACCOUNTING_INTEGRATION_MANAGE` gates every endpoint in
this router (Owner-only by default per plan §8)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, require_permission
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.rbac import Permission
from app.db.session import get_db
from app.repositories.activity import ActivityLogRepository
from app.schemas.accounting_connector import (
    AccountingConnectorCreate,
    AccountingConnectorRead,
    AccountingConnectorUpdate,
    ConnectorSyncInvoiceResult,
    ConnectorSyncLogRead,
    ConnectorTestConnectionResult,
)
from app.services.accounting_connectors.service import AccountingConnectorService

connector_router = APIRouter(prefix="/finance/connectors", tags=["finance-connectors"])


def _svc(db: AsyncSession = Depends(get_db)) -> AccountingConnectorService:
    return AccountingConnectorService(db)


def _to_http(err: Exception) -> HTTPException:
    if isinstance(err, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err.message)
    if isinstance(err, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err.message)
    if isinstance(err, ValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err.message)
    if isinstance(err, NotImplementedError):
        return HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(err))
    raise err


@connector_router.get("", response_model=list[AccountingConnectorRead])
async def list_connectors(
    workspace: WorkspaceContext = Depends(
        require_permission(Permission.ACCOUNTING_INTEGRATION_MANAGE)
    ),
    svc: AccountingConnectorService = Depends(_svc),
) -> list[AccountingConnectorRead]:
    items = await svc.list_for_agency(workspace.agency.id)
    return [AccountingConnectorRead.model_validate(i) for i in items]


@connector_router.post("", response_model=AccountingConnectorRead, status_code=201)
async def create_connector(
    data: AccountingConnectorCreate,
    workspace: WorkspaceContext = Depends(
        require_permission(Permission.ACCOUNTING_INTEGRATION_MANAGE)
    ),
    db: AsyncSession = Depends(get_db),
    svc: AccountingConnectorService = Depends(_svc),
) -> AccountingConnectorRead:
    try:
        connector = await svc.create(workspace.agency.id, workspace.user.id, data)
    except (NotFoundError, ConflictError, ValidationError) as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="accounting_connector.created",
        entity_type="accounting_connector",
        entity_id=connector.id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={"provider": connector.provider},
    )
    await db.commit()
    return AccountingConnectorRead.model_validate(connector)


@connector_router.get("/{connector_id}", response_model=AccountingConnectorRead)
async def get_connector(
    connector_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(
        require_permission(Permission.ACCOUNTING_INTEGRATION_MANAGE)
    ),
    svc: AccountingConnectorService = Depends(_svc),
) -> AccountingConnectorRead:
    try:
        connector = await svc.get(workspace.agency.id, connector_id)
    except NotFoundError as err:
        raise _to_http(err) from err
    return AccountingConnectorRead.model_validate(connector)


@connector_router.patch("/{connector_id}", response_model=AccountingConnectorRead)
async def update_connector(
    connector_id: uuid.UUID,
    data: AccountingConnectorUpdate,
    workspace: WorkspaceContext = Depends(
        require_permission(Permission.ACCOUNTING_INTEGRATION_MANAGE)
    ),
    db: AsyncSession = Depends(get_db),
    svc: AccountingConnectorService = Depends(_svc),
) -> AccountingConnectorRead:
    try:
        connector = await svc.update(workspace.agency.id, connector_id, data)
    except NotFoundError as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="accounting_connector.updated",
        entity_type="accounting_connector",
        entity_id=connector.id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={"provider": connector.provider, "fields": list(data.model_dump(exclude_unset=True))},
    )
    await db.commit()
    return AccountingConnectorRead.model_validate(connector)


@connector_router.delete("/{connector_id}", status_code=204, response_model=None)
async def delete_connector(
    connector_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(
        require_permission(Permission.ACCOUNTING_INTEGRATION_MANAGE)
    ),
    db: AsyncSession = Depends(get_db),
    svc: AccountingConnectorService = Depends(_svc),
) -> None:
    try:
        await svc.delete(workspace.agency.id, connector_id)
    except NotFoundError as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="accounting_connector.deleted",
        entity_type="accounting_connector",
        entity_id=connector_id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={},
    )
    await db.commit()


@connector_router.post(
    "/{connector_id}/test-connection", response_model=ConnectorTestConnectionResult
)
async def test_connection(
    connector_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(
        require_permission(Permission.ACCOUNTING_INTEGRATION_MANAGE)
    ),
    db: AsyncSession = Depends(get_db),
    svc: AccountingConnectorService = Depends(_svc),
) -> ConnectorTestConnectionResult:
    try:
        connected, log = await svc.test_connection(workspace.agency.id, connector_id)
    except (NotFoundError, ConflictError, NotImplementedError) as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="accounting_connector.test_connection",
        entity_type="accounting_connector",
        entity_id=connector_id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={"connected": connected, "sync_log_id": str(log.id)},
    )
    await db.commit()
    return ConnectorTestConnectionResult(connected=connected, tested_at=log.created_at)


@connector_router.post(
    "/{connector_id}/sync-invoice/{invoice_id}", response_model=ConnectorSyncInvoiceResult
)
async def sync_invoice(
    connector_id: uuid.UUID,
    invoice_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(
        require_permission(Permission.ACCOUNTING_INTEGRATION_MANAGE)
    ),
    db: AsyncSession = Depends(get_db),
    svc: AccountingConnectorService = Depends(_svc),
) -> ConnectorSyncInvoiceResult:
    try:
        external_id, log = await svc.sync_invoice(workspace.agency.id, connector_id, invoice_id)
    except (NotFoundError, ConflictError, NotImplementedError) as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="accounting_connector.sync_invoice",
        entity_type="client_invoice",
        entity_id=invoice_id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={
            "connector_id": str(connector_id),
            "external_invoice_id": external_id,
            "sync_log_id": str(log.id),
        },
    )
    await db.commit()
    return ConnectorSyncInvoiceResult(
        external_invoice_id=external_id,
        status=log.status,
        sync_log=ConnectorSyncLogRead.model_validate(log),
    )

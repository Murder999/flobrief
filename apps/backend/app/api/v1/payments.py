"""Payment recording endpoints (plan §9). `PAYMENT_VIEW`/`PAYMENT_MANAGE`
gate this router — Owner and Admin only per plan §8. Every mutating
endpoint writes an `ActivityLogRepository` row."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, require_permission
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.rbac import Permission
from app.db.session import get_db
from app.repositories.activity import ActivityLogRepository
from app.schemas.payment import PaymentCreate, PaymentRead
from app.services.payment_service import PaymentService

payment_router = APIRouter(prefix="/finance/payments", tags=["finance-payments"])


def _svc(db: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(db)


def _to_http(err: Exception) -> HTTPException:
    if isinstance(err, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err.message)
    if isinstance(err, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err.message)
    if isinstance(err, ValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err.message)
    raise err


@payment_router.get("", response_model=list[PaymentRead])
async def list_payments(
    brand_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    workspace: WorkspaceContext = Depends(require_permission(Permission.PAYMENT_VIEW)),
    svc: PaymentService = Depends(_svc),
) -> list[PaymentRead]:
    items = await svc.list_for_agency(workspace.agency.id, brand_id, invoice_id, limit, offset)
    return [PaymentRead.model_validate(i) for i in items]


@payment_router.post("", response_model=PaymentRead, status_code=201)
async def record_payment(
    data: PaymentCreate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.PAYMENT_MANAGE)),
    db: AsyncSession = Depends(get_db),
    svc: PaymentService = Depends(_svc),
) -> PaymentRead:
    try:
        payment = await svc.record_payment(workspace.agency.id, workspace.user.id, data)
    except (NotFoundError, ConflictError, ValidationError) as err:
        raise _to_http(err) from err

    await ActivityLogRepository(db).create(
        action="payment.recorded",
        entity_type="payment",
        entity_id=payment.id,
        agency_id=workspace.agency.id,
        brand_id=payment.brand_id,
        actor_user_id=workspace.user.id,
        meta={
            "amount_cents": payment.amount_cents,
            "currency": payment.currency,
            "invoice_id": str(payment.invoice_id) if payment.invoice_id else None,
        },
    )
    await db.commit()
    return PaymentRead.model_validate(payment)

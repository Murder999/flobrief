"""Regression guard for the Phase 7 RBAC/audit sweep.

Every mutating endpoint (POST/PUT/PATCH/DELETE) across the 8 new capacity +
finance router files must (a) gate on a `Permission` via
`require_permission(...)` (or the brand-portal auth context, for the one
router that intentionally uses a different auth mechanism) and (b) write an
`ActivityLogRepository(...).create(...)` audit-log row. This is verified by
static inspection of each route handler's own source — not a one-time
manual check — so a future endpoint added to any of these routers without
wiring both of these will fail this test, not silently ship ungated or
unaudited."""

from __future__ import annotations

import inspect

import pytest
from fastapi.routing import APIRoute

from app.api.v1.accounting_connectors import connector_router
from app.api.v1.brand_finance import brand_finance_router
from app.api.v1.capacity import capacity_router
from app.api.v1.commercial_terms import commercial_terms_router
from app.api.v1.cost_rates import cost_rates_router
from app.api.v1.invoices import invoice_router
from app.api.v1.payments import payment_router
from app.api.v1.profitability import profitability_router

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

_ROUTERS = {
    "capacity": capacity_router,
    "commercial_terms": commercial_terms_router,
    "cost_rates": cost_rates_router,
    "invoices": invoice_router,
    "accounting_connectors": connector_router,
    "payments": payment_router,
    "profitability": profitability_router,
    "brand_finance": brand_finance_router,
}

# Routers whose mutating endpoints are intentionally gated by something
# other than `require_permission(...)`. brand_finance has zero mutating
# endpoints today (read-only brand-portal invoice view) but is listed here
# defensively in case that ever changes without updating this test.
_NON_WORKSPACE_AUTH_ROUTERS = {"brand_finance"}


def _mutating_routes() -> list[tuple[str, APIRoute]]:
    routes: list[tuple[str, APIRoute]] = []
    for router_name, router in _ROUTERS.items():
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            if route.methods & _MUTATING_METHODS:
                routes.append((f"{router_name}:{sorted(route.methods)}:{route.path}", route))
    return routes


_ROUTES = _mutating_routes()
_IDS = [label for label, _ in _ROUTES]


def test_sweep_found_mutating_routes_in_every_router_expected_to_have_them() -> None:
    """Sanity check on the sweep itself: guards against the parametrized
    tests below silently passing on an empty set if FastAPI's route
    internals ever change shape."""
    covered = {label.split(":", 1)[0] for label, _ in _ROUTES}
    # profitability.py and brand_finance.py are entirely read-only (GET) by
    # design (plan §9, Phase 6 / brand-portal split) — they legitimately
    # contribute zero mutating routes.
    expected = {
        "capacity",
        "commercial_terms",
        "cost_rates",
        "invoices",
        "accounting_connectors",
        "payments",
    }
    assert covered == expected, (
        f"Expected mutating routes from {expected}, found from {covered}. "
        "If a router gained/lost its only mutating endpoint, update this test."
    )


@pytest.mark.parametrize("label,route", _ROUTES, ids=_IDS)
def test_mutating_endpoint_has_permission_gate(label: str, route: APIRoute) -> None:
    router_name = label.split(":", 1)[0]
    source = inspect.getsource(route.endpoint)
    if router_name in _NON_WORKSPACE_AUTH_ROUTERS:
        assert "get_brand_portal_context" in source, f"{label} has no recognized auth-context gate"
        return
    assert (
        "require_permission(Permission." in source
    ), f"{label} has no require_permission(Permission....) gate on its handler signature"


@pytest.mark.parametrize("label,route", _ROUTES, ids=_IDS)
def test_mutating_endpoint_writes_audit_log(label: str, route: APIRoute) -> None:
    source = inspect.getsource(route.endpoint)
    assert "ActivityLogRepository(db).create(" in source, (
        f"{label} does not call ActivityLogRepository(db).create(...) — "
        "every mutation in these routers must write an audit-log row"
    )


@pytest.mark.parametrize("label,route", _ROUTES, ids=_IDS)
def test_audit_log_meta_never_references_raw_credentials(label: str, route: APIRoute) -> None:
    """Defense-in-depth: the audit `meta` dict built inside a mutating
    handler must never pass through a raw credentials/secret field. This
    doesn't prove the meta dict is safe (services may still leak via other
    means, covered by security tests elsewhere) but it catches the most
    direct mistake — a handler stuffing `data.encrypted_credentials` or
    similar straight into `meta={...}`."""
    source = inspect.getsource(route.endpoint)
    forbidden_substrings = (
        "encrypted_credentials",
        'credentials":',
        '"password',
        '"secret',
        '"api_key',
        '"token":',
    )
    for needle in forbidden_substrings:
        assert needle not in source, f"{label} appears to reference {needle!r} in its handler body"

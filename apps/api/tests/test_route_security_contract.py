from collections.abc import Iterator

from fastapi import APIRouter
from fastapi.routing import APIRoute

from coeus.api.dependencies import get_csrf_validated_session
from coeus.api.routes import (
    access,
    admin,
    analyst,
    auth,
    feedback,
    notifications,
    qc,
    rfi_search,
    routing,
    similar_requests,
    store,
    store_files,
    tickets,
    users_admin,
)

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
PUBLIC_MUTATION_EXCEPTIONS = frozenset(
    {
        ("POST", "/auth/login"),
        ("POST", "/auth/register"),
    }
)
ROUTERS = (
    access.router,
    admin.router,
    analyst.router,
    auth.router,
    feedback.router,
    notifications.router,
    qc.router,
    rfi_search.router,
    routing.router,
    similar_requests.router,
    store.router,
    store_files.router,
    tickets.router,
    users_admin.router,
)


def test_authenticated_mutations_require_csrf_validation() -> None:
    missing_csrf: list[str] = []

    for route in _routes(ROUTERS):
        methods = route.methods or set()
        for method in sorted(methods & MUTATING_METHODS):
            if (method, route.path) in PUBLIC_MUTATION_EXCEPTIONS:
                continue
            if get_csrf_validated_session not in set(_dependency_calls(route)):
                missing_csrf.append(f"{method} {route.path}")

    assert missing_csrf == []


def _routes(routers: tuple[APIRouter, ...]) -> Iterator[APIRoute]:
    for router in routers:
        for route in router.routes:
            if isinstance(route, APIRoute):
                yield route


def _dependency_calls(route: APIRoute) -> Iterator[object]:
    stack = list(route.dependant.dependencies)
    while stack:
        dependency = stack.pop()
        yield dependency.call
        stack.extend(dependency.dependencies)

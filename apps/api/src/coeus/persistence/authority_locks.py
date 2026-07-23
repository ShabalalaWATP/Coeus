"""Canonical PostgreSQL lock order for mutable authority namespaces."""

from collections.abc import Iterable
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

AUTHORITY_NAMESPACE_ORDER = ("users", "sessions", "access", "teams")


def lock_authority_namespaces(
    connection: Connection,
    namespaces: Iterable[str],
) -> dict[str, dict[str, Any]]:
    """Lock requested state rows in the one global authority order."""
    requested = frozenset(namespaces)
    unknown = requested.difference(AUTHORITY_NAMESPACE_ORDER)
    if unknown:
        raise ValueError(f"Unknown authority namespaces: {', '.join(sorted(unknown))}")
    return {
        namespace: _lock_namespace(connection, namespace)
        for namespace in AUTHORITY_NAMESPACE_ORDER
        if namespace in requested
    }


def _lock_namespace(connection: Connection, namespace: str) -> dict[str, Any]:
    payload = connection.execute(
        text("SELECT payload FROM coeus_state WHERE namespace = :namespace FOR UPDATE"),
        {"namespace": namespace},
    ).scalar_one_or_none()
    return dict(payload) if payload is not None else {}

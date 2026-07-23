"""Lock and evaluate live workflow authority in PostgreSQL."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.access import ProductStatus
from coeus.domain.workflow_authority import (
    WorkflowCommitAuthority,
    WorkflowCommitResult,
    WorkflowProductVisibility,
    workflow_authority_result,
)
from coeus.persistence.authority_locks import lock_authority_namespaces
from coeus.persistence.codec import decode_value


def lock_workflow_authority(
    connection: Connection, authority: WorkflowCommitAuthority
) -> WorkflowCommitResult:
    """Lock authority state in users, sessions, access, teams, products order."""
    required_namespaces = {"users"}
    if authority.expected_session is not None:
        required_namespaces.add("sessions")
    if authority.rfi is not None or authority.qc is not None:
        required_namespaces.add("access")
    if authority.qc is not None:
        required_namespaces.add("teams")
    payloads = lock_authority_namespaces(connection, required_namespaces)
    users = _decoded(payloads["users"], "users")
    sessions = _decoded(payloads.get("sessions", {}), "sessions")
    access = payloads.get("access", {})
    acgs = _decoded(access, "acgs")
    memberships = _decoded(access, "memberships")
    teams = _decoded(payloads.get("teams", {}), "items")
    products = _lock_products(connection, authority)
    return workflow_authority_result(
        users,
        sessions,
        acgs,
        memberships,
        teams,
        products,
        authority,
    )


def _decoded(payload: dict[str, Any], key: str) -> tuple[Any, ...]:
    return tuple(decode_value(item) for item in payload.get(key, []))


def _lock_products(
    connection: Connection, authority: WorkflowCommitAuthority
) -> tuple[WorkflowProductVisibility, ...]:
    product_ids = authority.rfi.persisted_product_ids if authority.rfi is not None else frozenset()
    if not product_ids:
        return ()
    rows = connection.execute(
        text(
            """
            SELECT product_id, status, classification_level, acg_ids
            FROM intelligence_store_products
            WHERE product_id = ANY(CAST(:product_ids AS uuid[]))
            ORDER BY product_id
            FOR UPDATE
            """
        ),
        {"product_ids": [str(product_id) for product_id in sorted(product_ids, key=str)]},
    ).mappings()
    return tuple(_product_visibility(row) for row in rows)


def _product_visibility(row: Any) -> WorkflowProductVisibility:
    return WorkflowProductVisibility(
        product_id=UUID(str(row["product_id"])),
        status=ProductStatus(str(row["status"])),
        classification_level=int(row["classification_level"]),
        acg_ids=frozenset(UUID(str(acg_id)) for acg_id in row["acg_ids"]),
    )

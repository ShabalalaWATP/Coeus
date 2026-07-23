"""All PostgreSQL authority paths use one non-cyclic namespace lock order."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from coeus.domain.access import ProductStatus
from coeus.domain.auth import RoleName, SessionRecord, UserAccount
from coeus.domain.workflow_authority import (
    QcCommitAuthority,
    RfiCommitAuthority,
    WorkflowCommitAuthority,
)
from coeus.persistence.authority_locks import lock_authority_namespaces
from coeus.persistence.submission_authority import lock_submission_authority
from coeus.persistence.workflow_authority import _lock_products, lock_workflow_authority


class _EmptyResult:
    def scalar_one_or_none(self) -> None:
        return None


class _RecordingConnection:
    def __init__(self) -> None:
        self.namespaces: list[str] = []

    def execute(self, _statement: object, parameters: dict[str, Any]) -> _EmptyResult:
        self.namespaces.append(str(parameters["namespace"]))
        return _EmptyResult()


class _ProductResult:
    def __init__(self, row: dict[str, object]) -> None:
        self._row = row

    def mappings(self) -> tuple[dict[str, object], ...]:
        return (self._row,)


class _ProductConnection:
    def __init__(self, row: dict[str, object]) -> None:
        self.row = row
        self.product_ids: list[str] = []

    def execute(self, _statement: object, parameters: dict[str, Any]) -> _ProductResult:
        self.product_ids = list(parameters["product_ids"])
        return _ProductResult(self.row)


def test_workflow_and_submission_authority_share_one_namespace_order() -> None:
    actor = UserAccount(
        uuid4(),
        "lock-order@example.test",
        "Lock Order",
        frozenset({RoleName.USER}),
        frozenset(),
        "synthetic-hash",
        True,
        1,
    )
    session = SessionRecord(
        "session",
        actor.user_id,
        "csrf",
        datetime.now(UTC) + timedelta(hours=1),
        datetime.now(UTC),
    )
    workflow = _RecordingConnection()
    lock_workflow_authority(
        workflow,  # type: ignore[arg-type]
        WorkflowCommitAuthority(
            actor,
            session,
            frozenset(),
            rfi=RfiCommitAuthority(actor, frozenset(), frozenset()),
            qc=QcCommitAuthority(0, frozenset(), 0, frozenset(), None),
        ),
    )
    submission = _RecordingConnection()
    lock_submission_authority(
        submission,  # type: ignore[arg-type]
        actor.user_id,
        frozenset(),
    )

    assert workflow.namespaces == ["users", "sessions", "access", "teams"]
    assert submission.namespaces == ["users", "access"]


def test_authority_lock_rejects_unknown_namespaces() -> None:
    with pytest.raises(ValueError, match="Unknown authority namespaces: invalid"):
        lock_authority_namespaces(
            _RecordingConnection(),  # type: ignore[arg-type]
            ("users", "invalid"),
        )


def test_rfi_authority_locks_and_decodes_persisted_products() -> None:
    actor = _actor()
    product_id = uuid4()
    acg_id = uuid4()
    connection = _ProductConnection(
        {
            "product_id": product_id,
            "status": ProductStatus.PUBLISHED.value,
            "classification_level": 2,
            "acg_ids": [acg_id],
        }
    )
    authority = WorkflowCommitAuthority(
        actor,
        None,
        frozenset(),
        rfi=RfiCommitAuthority(actor, frozenset(), frozenset({product_id})),
    )

    products = _lock_products(connection, authority)  # type: ignore[arg-type]

    assert connection.product_ids == [str(product_id)]
    assert products[0].product_id == product_id
    assert products[0].status is ProductStatus.PUBLISHED
    assert products[0].classification_level == 2
    assert products[0].acg_ids == frozenset({acg_id})


def _actor() -> UserAccount:
    return UserAccount(
        uuid4(),
        "product-lock@example.test",
        "Product Lock",
        frozenset({RoleName.USER}),
        frozenset(),
        "synthetic-hash",
        True,
        2,
    )

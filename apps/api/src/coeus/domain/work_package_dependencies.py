"""Reviewed, version-bound work-package dependency commands."""

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from uuid import UUID


class DependencyOperation(StrEnum):
    ADD = "add"
    REMOVE = "remove"


class WorkPackageDependencyDenied(PermissionError):
    pass


class WorkPackageDependencyConflict(ValueError):
    pass


@dataclass(frozen=True)
class DependencyChangeRequest:
    unit_id: UUID
    package_id: UUID
    predecessor_package_id: UUID
    operation: DependencyOperation
    expected_package_version: int
    expected_predecessor_version: int
    expected_ownership_version: int
    authorising_grant_id: UUID
    expected_grant_version: int

    def __post_init__(self) -> None:
        if (
            min(
                self.expected_package_version,
                self.expected_predecessor_version,
                self.expected_ownership_version,
                self.expected_grant_version,
            )
            < 1
        ):
            raise ValueError("dependency evidence versions must be positive")
        if self.package_id == self.predecessor_package_id:
            raise ValueError("a work package cannot depend on itself")


@dataclass(frozen=True)
class DependencyChangePreview:
    preview_hash: str
    package_id: UUID
    package_version: int
    predecessor_package_id: UUID
    predecessor_package_version: int
    ownership_version: int
    dependency_active: bool
    planned_package_version: int


@dataclass(frozen=True)
class ChangeDependencyCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    request: DependencyChangeRequest
    preview_hash: str

    def __post_init__(self) -> None:
        if not 1 <= len(self.idempotency_key) <= 128:
            raise ValueError("dependency idempotency key is invalid")
        if len(self.preview_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.preview_hash
        ):
            raise ValueError("dependency preview hash is invalid")


@dataclass(frozen=True)
class DependencyChangeResult:
    package_id: UUID
    package_version: int
    predecessor_package_id: UUID
    dependency_active: bool
    replayed: bool


def dependency_change_hash(actor_user_id: UUID, request: DependencyChangeRequest) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        "authorising_grant_id": str(request.authorising_grant_id),
        "expected_grant_version": request.expected_grant_version,
        "expected_ownership_version": request.expected_ownership_version,
        "expected_package_version": request.expected_package_version,
        "expected_predecessor_version": request.expected_predecessor_version,
        "operation": request.operation.value,
        "package_id": str(request.package_id),
        "predecessor_package_id": str(request.predecessor_package_id),
        "unit_id": str(request.unit_id),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def validate_bounded_dependency_graph(
    package_ids: tuple[UUID, ...], edges: tuple[tuple[UUID, UUID], ...]
) -> None:
    """Validate a complete, bounded graph where each edge is (package, predecessor)."""
    if len(package_ids) > 128 or len(edges) > 512:
        raise WorkPackageDependencyDenied("dependency graph exceeds the review boundary")
    known = set(package_ids)
    if len(known) != len(package_ids):
        raise WorkPackageDependencyConflict("dependency graph contains duplicate packages")
    graph: dict[UUID, list[UUID]] = {package_id: [] for package_id in package_ids}
    _populate_graph(graph, known, edges)
    visiting: set[UUID] = set()
    visited: set[UUID] = set()

    def visit(package_id: UUID) -> None:
        if package_id in visiting:
            raise WorkPackageDependencyConflict("work-package dependencies must be acyclic")
        if package_id in visited:
            return
        visiting.add(package_id)
        for predecessor_id in graph[package_id]:
            visit(predecessor_id)
        visiting.remove(package_id)
        visited.add(package_id)

    for package_id in package_ids:
        visit(package_id)


def _populate_graph(
    graph: dict[UUID, list[UUID]],
    known: set[UUID],
    edges: tuple[tuple[UUID, UUID], ...],
) -> None:
    for package_id, predecessor_id in edges:
        if package_id not in known or predecessor_id not in known:
            raise WorkPackageDependencyDenied("dependency graph is incomplete")
        if package_id == predecessor_id:
            raise WorkPackageDependencyConflict("a work package cannot depend on itself")
        graph[package_id].append(predecessor_id)

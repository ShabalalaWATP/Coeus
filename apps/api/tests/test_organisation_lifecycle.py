from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from coeus.domain.organisation import (
    ManagementAction,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationUnit,
)
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationConflict,
    OrganisationMutationDenied,
    OrganisationMutationOperation,
    OrganisationMutationRequest,
    OrganisationMutationResult,
)
from coeus.services.organisation_lifecycle import OrganisationLifecycleService

NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)


class _Organisation:
    def __init__(
        self, units: tuple[OrganisationUnit, ...], grants: tuple[OrganisationManagementGrant, ...]
    ) -> None:
        self.units = {unit.unit_id: unit for unit in units}
        self.grants = {grant.grant_id: grant for grant in grants}

    def get_unit(self, unit_id: UUID):  # type: ignore[no-untyped-def]
        return self.units.get(unit_id)

    def effective_grants(self, manager_id: UUID, at: datetime):  # type: ignore[no-untyped-def]
        return tuple(
            grant
            for grant in self.grants.values()
            if grant.manager_user_id == manager_id
            and grant.valid_from <= at
            and grant.revoked_at is None
        )

    def get_management_grant(self, grant_id: UUID):  # type: ignore[no-untyped-def]
        return self.grants.get(grant_id)

    def unit_is_within(self, root_id: UUID, target_id: UUID) -> bool:
        return root_id == target_id


class _Store:
    def __init__(self) -> None:
        self.command: OrganisationMutationCommand | None = None
        self.replayed: OrganisationMutationResult | None = None

    def replay(self, command: OrganisationMutationCommand):  # type: ignore[no-untyped-def]
        return self.replayed

    def apply(self, command: OrganisationMutationCommand) -> OrganisationMutationResult:
        self.command = command
        version = 1 if command.request.operation is OrganisationMutationOperation.CREATE else 2
        return OrganisationMutationResult(command.request.unit_id, version, None)


def _unit(*, active: bool = True, version: int = 1) -> OrganisationUnit:
    return OrganisationUnit(
        uuid4(),
        "Synthetic Root",
        "Root",
        OrganisationCategory.COMMAND,
        None,
        NOW,
        is_active=active,
        version=version,
    )


def _grant(actor_id: UUID, root_id: UUID, action: ManagementAction) -> OrganisationManagementGrant:
    return OrganisationManagementGrant(
        uuid4(), actor_id, root_id, action, True, NOW, actor_id, "Synthetic authority"
    )


def _request(
    operation: OrganisationMutationOperation,
    unit: OrganisationUnit,
    grant: OrganisationManagementGrant,
) -> OrganisationMutationRequest:
    return OrganisationMutationRequest(
        operation,
        uuid4() if operation is OrganisationMutationOperation.CREATE else unit.unit_id,
        unit.unit_id if operation is OrganisationMutationOperation.CREATE else None,
        unit.version,
        "Synthetic Child" if operation is OrganisationMutationOperation.CREATE else "Renamed Root",
        "Child" if operation is OrganisationMutationOperation.CREATE else "Renamed",
        OrganisationCategory.COMMAND,
        "Europe/London",
        "Synthetic metadata",
        grant.grant_id,
        "Approved synthetic change",
    )


def test_create_preview_is_actor_bound_and_execute_is_idempotent() -> None:
    actor_id = uuid4()
    root = _unit()
    grant = _grant(actor_id, root.unit_id, ManagementAction.ORGANISATION_CREATE)
    store = _Store()
    service = OrganisationLifecycleService(
        _Organisation((root,), (grant,)),
        store,
        clock=lambda: NOW,  # type: ignore[arg-type]
    )
    request = _request(OrganisationMutationOperation.CREATE, root, grant)
    preview = service.preview(request, actor_id)
    command = OrganisationMutationCommand(
        uuid4(), "create-child", actor_id, request, preview.preview_hash
    )
    assert service.execute(command).version == 1
    assert store.command == command
    with pytest.raises(OrganisationMutationConflict, match="preview"):
        service.execute(replace(command, actor_user_id=uuid4()))
    store.replayed = OrganisationMutationResult(request.unit_id, 1, uuid4(), True)
    assert service.execute(command).replayed


def test_preview_rejects_missing_stale_duplicate_or_unauthorised_create() -> None:
    actor_id = uuid4()
    root = _unit()
    grant = _grant(actor_id, root.unit_id, ManagementAction.ORGANISATION_CREATE)
    request = _request(OrganisationMutationOperation.CREATE, root, grant)
    store = _Store()
    with pytest.raises(OrganisationMutationConflict, match="parent unit"):
        OrganisationLifecycleService(  # type: ignore[arg-type]
            _Organisation((), (grant,)), store, clock=lambda: NOW
        ).preview(request, actor_id)
    inactive = replace(root, is_active=False)
    with pytest.raises(OrganisationMutationConflict, match="parent unit"):
        OrganisationLifecycleService(  # type: ignore[arg-type]
            _Organisation((inactive,), (grant,)), store, clock=lambda: NOW
        ).preview(request, actor_id)
    with pytest.raises(OrganisationMutationConflict, match="version"):
        OrganisationLifecycleService(  # type: ignore[arg-type]
            _Organisation((replace(root, version=2),), (grant,)), store, clock=lambda: NOW
        ).preview(request, actor_id)
    duplicate = replace(root, unit_id=request.unit_id)
    with pytest.raises(OrganisationMutationConflict, match="already in use"):
        OrganisationLifecycleService(  # type: ignore[arg-type]
            _Organisation((root, duplicate), (grant,)), store, clock=lambda: NOW
        ).preview(request, actor_id)
    with pytest.raises(OrganisationMutationDenied):
        OrganisationLifecycleService(  # type: ignore[arg-type]
            _Organisation((root,), ()), store, clock=lambda: NOW
        ).preview(request, actor_id)


def test_edit_preview_rejects_invalid_or_unchanged_metadata() -> None:
    actor_id = uuid4()
    unit = _unit()
    grant = _grant(actor_id, unit.unit_id, ManagementAction.ORGANISATION_EDIT)
    request = _request(OrganisationMutationOperation.EDIT, unit, grant)
    service = OrganisationLifecycleService(  # type: ignore[arg-type]
        _Organisation((unit,), (grant,)), _Store(), clock=lambda: NOW
    )
    assert service.preview(request, actor_id).scope_unit_id == unit.unit_id
    with pytest.raises(OrganisationMutationConflict, match="category"):
        service.preview(replace(request, category=OrganisationCategory.OTHER), actor_id)
    unchanged = replace(
        request,
        name=unit.name,
        short_name=unit.short_name,
        category=unit.category,
        time_zone=unit.time_zone,
        description=unit.description,
    )
    with pytest.raises(OrganisationMutationConflict, match="does not change"):
        service.preview(unchanged, actor_id)
    for invalid in ((), (replace(unit, is_active=False),)):
        with pytest.raises(OrganisationMutationConflict, match="not active"):
            OrganisationLifecycleService(  # type: ignore[arg-type]
                _Organisation(invalid, (grant,)), _Store(), clock=lambda: NOW
            ).preview(request, actor_id)


@pytest.mark.parametrize(
    "change",
    (
        {"expected_version": 0},
        {"name": ""},
        {"reason": ""},
    ),
)
def test_mutation_request_rejects_invalid_fields(change: dict[str, object]) -> None:
    actor_id = uuid4()
    root = _unit()
    grant = _grant(actor_id, root.unit_id, ManagementAction.ORGANISATION_CREATE)
    with pytest.raises(ValueError):
        replace(_request(OrganisationMutationOperation.CREATE, root, grant), **change)


def test_mutation_request_and_command_enforce_shape() -> None:
    actor_id = uuid4()
    root = _unit()
    grant = _grant(actor_id, root.unit_id, ManagementAction.ORGANISATION_CREATE)
    request = _request(OrganisationMutationOperation.CREATE, root, grant)
    with pytest.raises(ValueError, match="requires parent"):
        replace(request, parent_unit_id=None)
    with pytest.raises(ValueError, match="cannot change parent"):
        replace(request, operation=OrganisationMutationOperation.EDIT)
    with pytest.raises(ValueError, match="parent itself"):
        replace(request, unit_id=root.unit_id)
    for key in ("", " key", "x" * 129, "bad\nkey"):
        with pytest.raises(ValueError):
            OrganisationMutationCommand(uuid4(), key, actor_id, request, "a" * 64)
    with pytest.raises(ValueError, match="preview_hash"):
        OrganisationMutationCommand(uuid4(), "key", actor_id, request, "not-a-hash")

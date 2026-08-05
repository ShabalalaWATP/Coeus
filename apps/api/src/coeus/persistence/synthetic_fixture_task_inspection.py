"""Conflict-first inspection of synthetic task and workload rows."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureFinding,
    SyntheticFixtureUser,
)
from coeus.persistence.synthetic_fixture_inspection_common import classify, finding, material, row
from coeus.persistence.synthetic_fixture_values import PROVENANCE, topology_revision_id
from coeus.repositories.synthetic_organisation_manifest import BASELINE, synthetic_unit_specs
from coeus.repositories.synthetic_task_manifest import SyntheticTaskSpec, synthetic_task_specs
from coeus.repositories.synthetic_task_values import encoded_ticket, package_values

PackagePlan = tuple[SyntheticTaskSpec, int]


def inspect_tasks(
    connection: Connection,
    users: dict[str, SyntheticFixtureUser],
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> tuple[list[SyntheticTaskSpec], list[SyntheticTaskSpec], list[PackagePlan]]:
    unit_ids = {item.key: item.unit_id for item in synthetic_unit_specs()}
    user_ids = {key: value.user_id for key, value in users.items()}
    missing_tasks: list[SyntheticTaskSpec] = []
    missing_ownership: list[SyntheticTaskSpec] = []
    missing_packages: list[PackagePlan] = []
    for spec in synthetic_task_specs():
        _inspect_task(
            connection,
            spec,
            user_ids,
            unit_ids,
            findings,
            state,
            creates,
            unchanged,
            missing_tasks,
        )
        _inspect_ownership(
            connection,
            spec,
            user_ids,
            unit_ids,
            findings,
            state,
            creates,
            unchanged,
            missing_ownership,
        )
        for order in (1, 2):
            _inspect_package(
                connection,
                spec,
                order,
                user_ids,
                unit_ids,
                findings,
                state,
                creates,
                unchanged,
                missing_packages,
            )
    return missing_tasks, missing_ownership, missing_packages


def _inspect_task(
    connection: Connection,
    spec: SyntheticTaskSpec,
    users: dict[str, UUID],
    units: dict[str, UUID],
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
    missing: list[SyntheticTaskSpec],
) -> None:
    expected_ticket = encoded_ticket(spec, users, units)
    existing = row(connection, "coeus_ticket_aggregates", "ticket_id", spec.ticket_id)
    reference_owner = connection.execute(
        text(
            "SELECT ticket_id FROM coeus_ticket_aggregates "
            "WHERE payload->'fields'->>'reference'=:reference AND ticket_id<>:ticket_id"
        ),
        {"reference": spec.reference, "ticket_id": spec.ticket_id},
    ).first()
    state.append(("task", spec.key, material(existing), str(reference_owner)))
    if reference_owner is not None:
        findings.append(
            finding("task_reference_collision", "task", spec.key, "Task reference is in use.")
        )
        return
    classify(
        existing,
        {
            "requester_user_id": expected_ticket.record.requester_user_id,
            "state": spec.ticket_state.value,
            "consumes_capacity": not spec.ticket_state.value.startswith("CLOSED_"),
            "version": 1,
            "canonical_hash": expected_ticket.canonical_hash,
        },
        spec,
        "tasks",
        findings,
        missing,
        creates,
        unchanged,
    )


def _inspect_ownership(
    connection: Connection,
    spec: SyntheticTaskSpec,
    users: dict[str, UUID],
    units: dict[str, UUID],
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
    missing: list[SyntheticTaskSpec],
) -> None:
    existing = row(connection, "team_task_ownership", "ownership_id", spec.ownership_id)
    by_leg = connection.execute(
        text(
            "SELECT ownership_id FROM team_task_ownership "
            "WHERE ticket_id=:ticket_id AND workflow_leg=:leg"
        ),
        {"ticket_id": spec.ticket_id, "leg": spec.workflow_leg.value},
    ).first()
    state.append(("task_ownership", spec.key, material(existing), str(by_leg)))
    if existing is None and by_leg is not None:
        findings.append(
            finding(
                "task_ownership_collision",
                "task_ownership",
                spec.key,
                "Workflow leg is owned by another row.",
            )
        )
        return
    accepted = spec.ownership_state.value in {"accepted", "active", "completed"}
    classify(
        existing,
        {
            "ticket_id": spec.ticket_id,
            "workflow_leg": spec.workflow_leg.value,
            "owning_unit_id": units[spec.unit_key],
            "manager_user_id": users[spec.manager_username],
            "state": spec.ownership_state.value,
            "accepted_at": BASELINE - timedelta(days=6) if accepted else None,
            "target_date": spec.target_date,
            "topology_revision_id": topology_revision_id(units[spec.unit_key]),
            "capability_policy_version": 1,
            "version": 1,
            "history_reference": spec.history_reference,
            "provenance": PROVENANCE,
            "reason": "Synthetic exercise workload.",
        },
        spec,
        "task_ownership",
        findings,
        missing,
        creates,
        unchanged,
    )


def _inspect_package(
    connection: Connection,
    spec: SyntheticTaskSpec,
    order: int,
    users: dict[str, UUID],
    units: dict[str, UUID],
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
    missing: list[PackagePlan],
) -> None:
    package_id = spec.package_id(order)
    existing = row(connection, "canonical_work_packages", "package_id", package_id)
    values = package_values(spec, order)
    username = values.pop("accountable_username")
    expected = {
        "ticket_id": spec.ticket_id,
        "workflow_leg": spec.workflow_leg.value,
        "owning_unit_id": units[spec.unit_key],
        "accountable_user_id": users[str(username)] if username else None,
        **values,
        "priority_override_reason": "",
        "sort_order": order,
        "version": 1,
        "provenance": PROVENANCE,
    }
    evidence = _package_evidence(connection, spec, order, expected["accountable_user_id"])
    state.append(("work_package", spec.key, order, material(existing), evidence))
    planned = (spec, order)
    classify(
        existing,
        expected,
        planned,
        "work_packages",
        findings,
        missing,
        creates,
        unchanged,
    )
    if existing is not None and not all(evidence):
        findings.append(
            finding(
                "work_package_evidence_gap",
                "work_package",
                f"{spec.key}:{order}",
                "Supporting work-package evidence is incomplete.",
            )
        )


def _package_evidence(
    connection: Connection, spec: SyntheticTaskSpec, order: int, accountable_id: object
) -> tuple[bool, bool, bool, bool]:
    history = connection.execute(
        text("SELECT 1 FROM work_package_history WHERE history_id=:id"),
        {"id": spec.package_history_id(order)},
    ).first()
    command = connection.execute(
        text("SELECT 1 FROM work_package_commands WHERE command_id=:id"),
        {"id": spec.package_command_id(order)},
    ).first()
    participant = True
    if accountable_id is not None:
        participant = (
            connection.execute(
                text(
                    "SELECT 1 FROM work_package_participants WHERE package_id=:id "
                    "AND user_id=:user_id AND role='accountable' AND active"
                ),
                {"id": spec.package_id(order), "user_id": accountable_id},
            ).first()
            is not None
        )
    dependency = True
    if order == 2:
        dependency = (
            connection.execute(
                text(
                    "SELECT 1 FROM work_package_dependencies WHERE package_id=:id "
                    "AND predecessor_package_id=:predecessor"
                ),
                {"id": spec.package_id(2), "predecessor": spec.package_id(1)},
            ).first()
            is not None
        )
    return history is not None, command is not None, participant, dependency

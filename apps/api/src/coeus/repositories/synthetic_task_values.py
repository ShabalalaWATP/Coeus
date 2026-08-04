"""Canonical aggregate and work-package values for synthetic tasks."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.domain.tickets import (
    AnalystAssignment,
    AnalystWorkPackage,
    IntakeDetails,
    RoutingRoute,
    TicketRecord,
    WorkPackageStatus,
)
from coeus.domain.work_packages import CanonicalWorkPackageState
from coeus.persistence.codec import encode_value
from coeus.repositories.synthetic_organisation_manifest import BASELINE
from coeus.repositories.synthetic_task_manifest import SyntheticTaskSpec


@dataclass(frozen=True)
class SyntheticEncodedTicket:
    record: TicketRecord
    payload: str
    canonical_hash: str


def encoded_ticket(
    spec: SyntheticTaskSpec,
    user_ids: dict[str, UUID],
    unit_ids: dict[str, UUID],
) -> SyntheticEncodedTicket:
    created_at = BASELINE - timedelta(days=7)
    assignee_id = user_ids.get(spec.assignee_username or "")
    manager_id = user_ids[spec.manager_username]
    assignments: tuple[AnalystAssignment, ...] = ()
    if assignee_id is not None:
        assignments = (
            AnalystAssignment(
                _stable_id("embedded-assignment", spec.key),
                spec.ticket_id,
                assignee_id,
                manager_id,
                _routing_route(spec),
                created_at + timedelta(hours=2),
                unit_ids[spec.unit_key],
                spec.unit_key,
            ),
        )
    packages = tuple(
        AnalystWorkPackage(
            spec.package_id(order),
            spec.ticket_id,
            title,
            _embedded_package_status(spec, order),
            order,
            created_at + timedelta(hours=3),
        )
        for order, title in enumerate(_PACKAGE_TITLES, start=1)
    )
    record = TicketRecord(
        ticket_id=spec.ticket_id,
        reference=spec.reference,
        requester_user_id=user_ids[spec.requester_username],
        state=spec.ticket_state,
        intake=IntakeDetails(
            title=spec.title,
            description="Synthetic exercise requirement for team workflow validation.",
            operational_question=(
                f"What does the available exercise evidence show about {spec.title.lower()}?"
            ),
            priority=spec.priority,
            deadline=spec.target_date.isoformat(),
            required_output_format="Concise assessed brief",
            customer_success_criteria="A sourced assessment with confidence and caveats.",
            confidence=1.0,
        ),
        analyst_assignments=assignments,
        work_packages=packages,
        collect_disposition="collect" if spec.workflow_leg.value.startswith("cm_") else None,
        created_at=created_at,
        updated_at=BASELINE,
    )
    encoded = encode_value(record)
    payload = json.dumps(encoded, sort_keys=True, separators=(",", ":"))
    return SyntheticEncodedTicket(record, payload, sha256(payload.encode()).hexdigest())


def package_values(spec: SyntheticTaskSpec, order: int) -> dict[str, object]:
    state = _canonical_package_state(spec, order)
    estimate = {"Urgent": 600, "High": 480}.get(spec.priority, 360)
    remaining = 0 if state is CanonicalWorkPackageState.COMPLETE else estimate
    if state is CanonicalWorkPackageState.IN_PROGRESS:
        remaining //= 2
    accountable = spec.assignee_username if state is not CanonicalWorkPackageState.PENDING else None
    blocked = state is CanonicalWorkPackageState.BLOCKED
    return {
        "title": _PACKAGE_TITLES[order - 1],
        "state": state.value,
        "accountable_username": accountable,
        "estimated_minutes": estimate,
        "remaining_minutes": remaining,
        "due_at": datetime.combine(spec.target_date, datetime.min.time(), UTC),
        "priority": {"Urgent": 1, "High": 2}.get(spec.priority, 3),
        "blocked_code": "awaiting_external_evidence" if blocked else None,
        "blocked_note": "Awaiting a scheduled synthetic evidence release." if blocked else "",
        "review_at": BASELINE + timedelta(days=2) if blocked else None,
    }


def _canonical_package_state(spec: SyntheticTaskSpec, order: int) -> CanonicalWorkPackageState:
    if order == 1:
        return spec.package_state
    if spec.package_state is CanonicalWorkPackageState.COMPLETE:
        return CanonicalWorkPackageState.COMPLETE
    return CanonicalWorkPackageState.PENDING


def _embedded_package_status(spec: SyntheticTaskSpec, order: int) -> WorkPackageStatus:
    state = _canonical_package_state(spec, order)
    return (
        WorkPackageStatus.COMPLETE
        if state is CanonicalWorkPackageState.COMPLETE
        else WorkPackageStatus.PENDING
    )


def _routing_route(spec: SyntheticTaskSpec) -> RoutingRoute:
    return RoutingRoute.CM if spec.workflow_leg.value.startswith("cm_") else RoutingRoute.RFA


def _stable_id(kind: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"coeus:synthetic-{kind}:v1:{key}")


_PACKAGE_TITLES = ("Assess available evidence", "Produce and review assessed output")

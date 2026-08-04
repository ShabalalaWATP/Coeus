"""Cross-command idempotency rows fail closed when identifiers diverge."""

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import RowMapping

from coeus.domain.organisation import MembershipRole, OrganisationCategory
from coeus.domain.organisation_deactivation import (
    OrganisationDeactivationCommand,
    OrganisationDeactivationIdempotencyConflict,
    OrganisationDeactivationRequest,
)
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationIdempotencyConflict,
    OrganisationMutationOperation,
    OrganisationMutationRequest,
)
from coeus.domain.organisation_membership import (
    MembershipIdempotencyConflict,
    MembershipMutationCommand,
    MembershipMutationRequest,
    MembershipOperation,
)
from coeus.domain.organisation_reparent import (
    OrganisationReparentCommand,
    OrganisationReparentIdempotencyConflict,
    OrganisationReparentRequest,
)
from coeus.domain.organisation_transfer import (
    PersonnelTransferCommand,
    PersonnelTransferIdempotencyConflict,
    PersonnelTransferRequest,
)
from coeus.persistence.organisation_deactivation_postgres import _replay as deactivate_replay
from coeus.persistence.organisation_lifecycle_postgres import _replay as lifecycle_replay
from coeus.persistence.organisation_membership_postgres import _replay as membership_replay
from coeus.persistence.organisation_reparent_postgres import _replay as reparent_replay
from coeus.persistence.organisation_transfer_rows import replay as transfer_replay

NOW = datetime(2026, 8, 3, 16, tzinfo=UTC)
ROWS = cast(tuple[RowMapping, ...], ({}, {}))


def test_every_command_store_rejects_two_idempotency_rows() -> None:
    actor_id, grant_id = uuid4(), uuid4()
    lifecycle_request = OrganisationMutationRequest(
        OrganisationMutationOperation.CREATE,
        uuid4(),
        uuid4(),
        1,
        "Synthetic Unit",
        "Unit",
        OrganisationCategory.BRANCH,
        "Europe/London",
        "",
        grant_id,
        "Synthetic command.",
    )
    lifecycle = OrganisationMutationCommand(
        uuid4(), "lifecycle-collision", actor_id, lifecycle_request, "a" * 64
    )
    with pytest.raises(OrganisationMutationIdempotencyConflict):
        lifecycle_replay(ROWS, lifecycle)

    reparent = OrganisationReparentCommand(
        uuid4(),
        "reparent-collision",
        actor_id,
        OrganisationReparentRequest(uuid4(), uuid4(), 1, 1, grant_id, "Synthetic command."),
        "a" * 64,
    )
    with pytest.raises(OrganisationReparentIdempotencyConflict):
        reparent_replay(ROWS, reparent)

    membership = MembershipMutationCommand(
        uuid4(),
        "membership-collision",
        actor_id,
        MembershipMutationRequest(
            MembershipOperation.CREATE,
            uuid4(),
            uuid4(),
            uuid4(),
            0,
            MembershipRole.MEMBER,
            False,
            NOW,
            None,
            grant_id,
            "Synthetic command.",
        ),
        "a" * 64,
    )
    with pytest.raises(MembershipIdempotencyConflict):
        membership_replay(ROWS, membership)

    deactivation = OrganisationDeactivationCommand(
        uuid4(),
        "deactivation-collision",
        actor_id,
        OrganisationDeactivationRequest(uuid4(), 1, grant_id, "Synthetic command."),
        "a" * 64,
    )
    with pytest.raises(OrganisationDeactivationIdempotencyConflict):
        deactivate_replay(ROWS, deactivation)

    transfer = PersonnelTransferCommand(
        uuid4(),
        "transfer-collision",
        actor_id,
        PersonnelTransferRequest(
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
            1,
            1,
            MembershipRole.MEMBER,
            False,
            NOW + timedelta(days=1),
            grant_id,
            grant_id,
            "Synthetic command.",
        ),
        "a" * 64,
    )
    with pytest.raises(PersonnelTransferIdempotencyConflict):
        transfer_replay(ROWS, transfer)

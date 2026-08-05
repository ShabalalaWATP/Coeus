"""Domain and service contracts for cross-team workflow-leg transfer."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.workflow_leg_transfers import (
    PackageTransferDisposition,
    PackageTransferPlan,
    ProposeWorkflowLegTransfer,
    WorkflowLegTransferCommand,
    command_hash,
    proposal_hash,
)


def transfer_plan() -> PackageTransferPlan:
    start = datetime.now(UTC) + timedelta(days=1)
    return PackageTransferPlan(
        uuid4(),
        PackageTransferDisposition.TRANSFER,
        2,
        uuid4(),
        "target-capacity",
        start,
        start + timedelta(hours=2),
        120,
    )


def proposal() -> ProposeWorkflowLegTransfer:
    return ProposeWorkflowLegTransfer(
        uuid4(),
        uuid4(),
        WorkflowLeg.RFA,
        uuid4(),
        uuid4(),
        uuid4(),
        3,
        5,
        "a" * 64,
        uuid4(),
        2,
        datetime.now(UTC) + timedelta(days=2),
        (transfer_plan(), PackageTransferPlan(uuid4(), PackageTransferDisposition.RETAIN, 1)),
        "Capacity balancing",
    )


def test_proposal_binds_actor_and_all_dispositions() -> None:
    request = proposal()
    actor = uuid4()
    assert proposal_hash(actor, request) == proposal_hash(actor, request)
    assert proposal_hash(uuid4(), request) != proposal_hash(actor, request)


def test_transfer_requires_distinct_teams_and_a_transferred_package() -> None:
    request = proposal()
    with pytest.raises(ValueError, match="distinct teams"):
        ProposeWorkflowLegTransfer(
            request.transfer_id,
            request.ticket_id,
            request.workflow_leg,
            request.source_unit_id,
            request.source_unit_id,
            request.target_user_id,
            request.expected_ownership_version,
            request.expected_ticket_version,
            request.expected_ticket_source_hash,
            request.authorising_grant_id,
            request.expected_grant_version,
            request.expires_at,
            request.packages,
            request.reason,
        )
    with pytest.raises(ValueError, match="at least one"):
        ProposeWorkflowLegTransfer(
            request.transfer_id,
            request.ticket_id,
            request.workflow_leg,
            request.source_unit_id,
            request.target_unit_id,
            request.target_user_id,
            request.expected_ownership_version,
            request.expected_ticket_version,
            request.expected_ticket_source_hash,
            request.authorising_grant_id,
            request.expected_grant_version,
            request.expires_at,
            (PackageTransferPlan(uuid4(), PackageTransferDisposition.RETAIN, 1),),
            request.reason,
        )


def test_transfer_reservation_plan_is_all_or_nothing() -> None:
    with pytest.raises(ValueError, match="complete reservation plan"):
        PackageTransferPlan(uuid4(), PackageTransferDisposition.TRANSFER, 1)
    with pytest.raises(ValueError, match="complete reservation plan"):
        PackageTransferPlan(
            uuid4(),
            PackageTransferDisposition.CANCEL,
            1,
            uuid4(),
            "unexpected",
            datetime.now(UTC),
            datetime.now(UTC) + timedelta(hours=1),
            60,
        )


def test_command_hash_binds_actor_and_evidence() -> None:
    command = WorkflowLegTransferCommand(
        uuid4(),
        "accept-transfer",
        uuid4(),
        uuid4(),
        1,
        "accept",
        "b" * 64,
        uuid4(),
        2,
        uuid4(),
        3,
        4,
        "c" * 64,
    )
    assert command_hash(command) == command_hash(command)
    changed = WorkflowLegTransferCommand(
        command.command_id,
        command.idempotency_key,
        uuid4(),
        command.transfer_id,
        command.expected_transfer_version,
        command.action,
        command.preview_hash,
        command.grant_id,
        command.expected_grant_version,
        command.target_membership_id,
        command.expected_target_membership_version,
        command.expected_target_account_credential_version,
        command.expected_target_account_source_hash,
    )
    assert command_hash(changed) != command_hash(command)
    replay = WorkflowLegTransferCommand(
        uuid4(),
        "fresh-transport-key",
        command.actor_user_id,
        command.transfer_id,
        command.expected_transfer_version,
        command.action,
        command.preview_hash,
        command.grant_id,
        command.expected_grant_version,
        command.target_membership_id,
        command.expected_target_membership_version,
        command.expected_target_account_credential_version,
        command.expected_target_account_source_hash,
    )
    assert command_hash(replay) == command_hash(command)

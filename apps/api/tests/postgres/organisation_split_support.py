"""Shared builders for PostgreSQL organisation split evidence."""

from uuid import UUID, uuid4

from organisation_merge_support import grant_id

from coeus.domain.organisation import ManagementAction, OrganisationCategory
from coeus.domain.organisation_merge import (
    MergeDisposition,
    MergeDispositionAction,
    MergeRecordKind,
    MergeUnitVersion,
)
from coeus.domain.organisation_split import (
    OrganisationSplitPlan,
    OrganisationSplitRequest,
    SplitSuccessor,
)


def split_request(  # type: ignore[no-untyped-def]
    engine, repository, source_id: UUID, parent_id: UUID
) -> OrganisationSplitRequest:
    source = repository.get_unit(source_id)
    parent = repository.get_unit(parent_id)
    assert source is not None and parent is not None
    successors = tuple(
        SplitSuccessor(
            uuid4(),
            f"{colour} Successor",
            f"{colour} Suc",
            OrganisationCategory.DELIVERY_TEAM,
            "Europe/London",
            f"Synthetic {colour.casefold()} successor.",
        )
        for colour in ("Red", "Blue")
    )
    authority = grant_id(engine, ManagementAction.ORGANISATION_RESTRUCTURE)
    return OrganisationSplitRequest(
        MergeUnitVersion(source_id, source.version),
        MergeUnitVersion(parent_id, parent.version),
        successors,
        authority,
        authority,
        "Split the synthetic delivery team.",
    )


def split_plan(  # type: ignore[no-untyped-def]
    request: OrganisationSplitRequest,
    impact,
    membership_to_move: UUID | None = None,
) -> OrganisationSplitPlan:
    destinations = (request.successors[0].unit_id, request.successors[1].unit_id)
    dispositions = []
    for item in impact.records:
        target = replacement = None
        if item.kind is MergeRecordKind.MEMBERSHIP:
            action = (
                MergeDispositionAction.MOVE
                if membership_to_move is None or item.record_id == membership_to_move
                else MergeDispositionAction.END
            )
            if action is MergeDispositionAction.MOVE:
                target, replacement = destinations[0], uuid4()
        elif item.kind in {
            MergeRecordKind.CHILD_UNIT,
            MergeRecordKind.DELIVERY_PROFILE,
            MergeRecordKind.CAPABILITY,
        }:
            action, target = MergeDispositionAction.MOVE, destinations[0]
        elif item.kind is MergeRecordKind.TASK:
            action, target = MergeDispositionAction.MOVE, destinations[1]
        elif item.kind is MergeRecordKind.GRANT:
            action = MergeDispositionAction.REVOKE
        else:
            action = MergeDispositionAction.CANCEL
        dispositions.append(
            MergeDisposition(
                item.kind,
                item.record_id,
                item.version,
                action,
                target,
                replacement,
            )
        )
    return OrganisationSplitPlan(request, tuple(dispositions))

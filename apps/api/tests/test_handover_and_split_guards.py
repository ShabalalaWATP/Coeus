"""Replacement pairing on a handover and successor identity on a split."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from coeus.domain.organisation import OrganisationCategory
from coeus.domain.organisation_merge import MergeUnitVersion
from coeus.domain.organisation_split import OrganisationSplitRequest, SplitSuccessor
from coeus.domain.work_package_handovers import ReservationDisposition
from coeus.schemas.work_package_handovers import ReservationHandoverPayload


def _handover(**overrides: object) -> ReservationHandoverPayload:
    values: dict[str, object] = {
        "sourceReservationId": uuid4(),
        "expectedSourceVersion": 1,
        "disposition": ReservationDisposition.REPLACE,
        "replacementReservationId": uuid4(),
        "replacementIdempotencyKey": "handover-replacement-1",
    }
    values.update(overrides)
    return ReservationHandoverPayload.model_validate(values)


def test_a_replacing_handover_carries_both_pieces_of_replacement_evidence() -> None:
    assert _handover().replacement_reservation_id is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"replacementReservationId": None},
        {"replacementIdempotencyKey": None},
        {
            "disposition": ReservationDisposition.RELEASE,
            "replacementIdempotencyKey": "handover-replacement-1",
            "replacementReservationId": uuid4(),
        },
    ],
)
def test_replacement_evidence_must_match_its_disposition(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="must match its disposition"):
        _handover(**overrides)


def _successor(unit_id: object, name: str) -> SplitSuccessor:
    return SplitSuccessor(
        unit_id,  # type: ignore[arg-type]
        name,
        name[:8],
        OrganisationCategory.DELIVERY_TEAM,
        "Europe/London",
    )


def test_a_successor_cannot_replace_the_source_parent() -> None:
    parent_id = uuid4()

    with pytest.raises(ValueError, match="cannot replace the source parent"):
        OrganisationSplitRequest(
            MergeUnitVersion(uuid4(), 1),
            MergeUnitVersion(parent_id, 1),
            (_successor(parent_id, "Northern Cell"), _successor(uuid4(), "Southern Cell")),
            uuid4(),
            uuid4(),
            "Synthetic split for coverage of the parent guard.",
        )

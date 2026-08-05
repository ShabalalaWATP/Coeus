"""Replacement pairing rules on a predecessor cancellation disposition."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from coeus.domain.package_predecessor_cancellation import DependantDispositionAction
from coeus.schemas.package_predecessor_cancellation import DependantDispositionPayload


def _payload(**overrides: object) -> DependantDispositionPayload:
    values: dict[str, object] = {
        "dependantPackageId": uuid4(),
        "expectedVersion": 1,
        "action": DependantDispositionAction.REPLACE,
        "replacementPackageId": uuid4(),
        "expectedReplacementVersion": 1,
    }
    values.update(overrides)
    return DependantDispositionPayload.model_validate(values)


def test_a_replacement_disposition_accepts_a_paired_replacement() -> None:
    payload = _payload()

    assert payload.replacement_package_id is not None
    assert payload.expected_replacement_version == 1


@pytest.mark.parametrize(
    "overrides",
    [{"replacementPackageId": None}, {"expectedReplacementVersion": None}],
)
def test_a_replacement_identity_and_version_travel_together(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="must be supplied together"):
        _payload(**overrides)


def test_only_a_replacement_disposition_may_name_a_replacement() -> None:
    with pytest.raises(ValidationError, match="may identify a replacement"):
        _payload(action=DependantDispositionAction.CANCEL)


def test_a_non_replacement_disposition_needs_no_replacement() -> None:
    payload = _payload(
        action=DependantDispositionAction.CANCEL,
        replacementPackageId=None,
        expectedReplacementVersion=None,
    )

    assert payload.replacement_package_id is None

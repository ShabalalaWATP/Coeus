"""Branch coverage for reconciliation projection and lifecycle guards."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.organisation import MembershipRole, MembershipState, TeamMembership
from coeus.persistence.organisation_reconciliation_lifecycle import (
    end_absent_coverage,
    next_version,
    resolve_membership_identities,
    versioned_upsert,
)
from coeus.persistence.organisation_reconciliation_verification import projection_matches

NOW = datetime(2026, 8, 4, 9, tzinfo=UTC)


class _Result:
    def __init__(self, value: object) -> None:
        self.value = value

    def first(self) -> object:
        return self.value

    def mappings(self) -> "_Result":
        return self


class _Connection:
    def __init__(self, *values: object) -> None:
        self.values = list(values)

    def execute(self, _statement: object, _params: object = None) -> _Result:
        return _Result(self.values.pop(0) if self.values else None)


def _projection_plan() -> SimpleNamespace:
    unit = SimpleNamespace(unit_id=uuid4(), name="Unit")
    profile = SimpleNamespace(profile_id=uuid4(), route="rfa")
    coverage = SimpleNamespace(coverage_id=uuid4(), proficiency=3)
    membership = SimpleNamespace(membership_id=uuid4(), state="active")
    return SimpleNamespace(
        units=((unit, object()),),
        delivery_profiles=(profile,),
        capability_coverage=(coverage,),
        memberships=(membership,),
        checkpoint=SimpleNamespace(source_namespace="synthetic-v2"),
    )


@pytest.mark.parametrize("failed_check", range(6))
def test_projection_verification_fails_closed_for_each_projection(failed_check: int) -> None:
    values: list[object] = [(1,), (1,), (1,), (1,), None, None]
    values[failed_check] = (1,) if failed_check >= 4 else None
    assert not projection_matches(
        cast(Connection, _Connection(*values)),
        _projection_plan(),  # type: ignore[arg-type]
    )


def test_projection_verification_accepts_an_exact_projection() -> None:
    assert projection_matches(
        cast(Connection, _Connection((1,), (1,), (1,), (1,), None, None)),
        _projection_plan(),  # type: ignore[arg-type]
    )


def test_version_oracle_handles_new_changed_and_unsupported_targets() -> None:
    identity = uuid4()
    desired = {
        "unit_id": identity,
        "name": "Updated",
        "short_name": "U",
        "category": "delivery_team",
        "parent_unit_id": None,
        "is_active": True,
        "valid_from": NOW,
        "valid_until": None,
        "time_zone": "Europe/London",
        "description": None,
        "provenance": "synthetic-v2",
    }
    assert (
        next_version(
            cast(Connection, _Connection(None)),
            "organisation_units",
            "unit_id",
            identity,
            "version",
            desired,
        )
        == 1
    )
    stored = {**desired, "name": "Old", "version": 4}
    assert (
        next_version(
            cast(Connection, _Connection(cast(RowMapping, stored))),
            "organisation_units",
            "unit_id",
            identity,
            "version",
            desired,
        )
        == 5
    )
    with pytest.raises(ValueError, match="unsupported"):
        next_version(cast(Connection, _Connection()), "unknown", "id", identity, "version", desired)


def test_versioned_upsert_and_absent_coverage_fail_closed() -> None:
    unit = SimpleNamespace(
        unit_id=uuid4(),
        name="Unit",
        short_name="U",
        category="delivery_team",
        parent_unit_id=None,
        is_active=True,
        valid_from=NOW,
        valid_until=None,
        time_zone="Europe/London",
        description=None,
        provenance="synthetic-v2",
    )
    with pytest.raises(ValueError, match="identity or version"):
        versioned_upsert(
            cast(Connection, _Connection(None, None)),
            "INSERT INTO organisation_units VALUES (1)",
            unit,
            "unit",
            "organisation_units",
            "unit_id",
            "version",
        )
    plan = SimpleNamespace(
        delivery_profiles=(SimpleNamespace(profile_id=uuid4()),),
        capability_coverage=(SimpleNamespace(coverage_id=uuid4()),),
        effective_at=NOW,
        checkpoint=SimpleNamespace(source_namespace="synthetic-v2"),
    )
    with pytest.raises(ValueError, match="before its start"):
        end_absent_coverage(cast(Connection, _Connection((1,))), plan)  # type: ignore[arg-type]


def _membership() -> TeamMembership:
    return TeamMembership(
        uuid4(),
        uuid4(),
        uuid4(),
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        NOW,
        uuid4(),
        "Synthetic posting",
        "synthetic-v2",
    )


def test_membership_identity_resolution_rotates_terminal_postings() -> None:
    membership = _membership()
    terminal = cast(RowMapping, {"state": "ended", "valid_until": NOW})
    resolved = resolve_membership_identities(
        cast(Connection, _Connection(terminal, None)), (membership,), NOW
    )[0]
    assert resolved.membership_id != membership.membership_id
    assert resolved.valid_from == NOW

    missing_end = cast(RowMapping, {"state": "ended", "valid_until": None})
    with pytest.raises(ValueError, match="missing its end time"):
        resolve_membership_identities(
            cast(Connection, _Connection(missing_end)), (membership,), NOW
        )

    with pytest.raises(ValueError, match="supported depth"):
        resolve_membership_identities(
            cast(Connection, _Connection(*([terminal] * 32))), (membership,), NOW
        )

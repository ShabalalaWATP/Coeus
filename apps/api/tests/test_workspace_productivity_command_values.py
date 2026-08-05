"""Payload coercion for workspace productivity commands."""

from uuid import uuid4

import pytest

from coeus.persistence.workspace_productivity_commands import integer_value, uuid_value


def test_a_uuid_is_read_from_an_object_or_its_text_form() -> None:
    value = uuid4()

    assert uuid_value({"view_id": value}, "view_id") == value
    assert uuid_value({"view_id": str(value)}, "view_id") == value


@pytest.mark.parametrize("payload", [{}, {"view_id": None}, {"view_id": "not-a-uuid"}])
def test_a_missing_or_malformed_uuid_is_refused_by_name(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="view_id is invalid"):
        uuid_value(payload, "view_id")


def test_an_integer_is_read_from_a_number_or_its_text_form() -> None:
    assert integer_value({"expected_version": 3}, "expected_version") == 3
    assert integer_value({"expected_version": "3"}, "expected_version") == 3
    assert integer_value({"expected_version": 3.0}, "expected_version") == 3


def test_an_optional_integer_may_be_absent_but_a_required_one_may_not() -> None:
    assert integer_value({}, "priority", optional=True) is None
    assert integer_value({"priority": None}, "priority", optional=True) is None
    with pytest.raises(ValueError, match="priority is invalid"):
        integer_value({}, "priority")


@pytest.mark.parametrize(
    "value",
    [True, False, "three", [3], {"value": 3}],
)
def test_a_value_that_is_not_a_plain_number_is_refused(value: object) -> None:
    # A boolean is an int in Python, so it is rejected explicitly rather than
    # silently becoming one or zero.
    with pytest.raises(ValueError, match="expected_version is invalid"):
        integer_value({"expected_version": value}, "expected_version")

import pytest

from coeus.services import strict_json
from coeus.services.strict_json import MAX_STRICT_JSON_NESTING, load_unique_json


def test_strict_json_accepts_exact_depth_and_ignores_delimiters_in_strings() -> None:
    exact = "[" * MAX_STRICT_JSON_NESTING + "0" + "]" * MAX_STRICT_JSON_NESTING

    assert load_unique_json(exact) is not None
    assert load_unique_json(r'{"text":"[{\"nested\":true}]"}') == {"text": '[{"nested":true}]'}


def test_strict_json_rejects_nesting_before_the_decoder_recurses() -> None:
    excessive = "[" * (MAX_STRICT_JSON_NESTING + 1) + "0" + "]" * (MAX_STRICT_JSON_NESTING + 1)

    with pytest.raises(ValueError, match="nesting exceeds"):
        load_unique_json(excessive)


def test_strict_json_normalises_decoder_recursion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def recurse(*_args: object, **_kwargs: object) -> object:
        raise RecursionError("synthetic decoder recursion")

    monkeypatch.setattr(strict_json.json, "loads", recurse)

    with pytest.raises(ValueError, match="nesting exceeds"):
        load_unique_json("{}")

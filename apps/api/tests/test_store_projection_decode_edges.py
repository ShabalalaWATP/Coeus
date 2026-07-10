import json
from datetime import UTC, date, datetime
from uuid import uuid4

from coeus.persistence.store_projection_decode import (
    _date_text,
    _datetime,
    _decode_bounding_box,
    _iter_values,
    _optional_text,
    _uuid,
)


def test_bounding_box_decoder_handles_null_invalid_and_json_values() -> None:
    assert _decode_bounding_box(None) is None
    assert _decode_bounding_box([1, 2, 3, 4]) is None

    bounding_box = _decode_bounding_box(
        json.dumps({"west": -5.0, "south": 50.0, "east": 1.0, "north": 55.0})
    )

    assert bounding_box is not None
    assert bounding_box.west == -5.0


def test_projection_scalar_decoders_accept_supported_database_shapes() -> None:
    identifier = uuid4()
    moment = datetime(2026, 7, 10, 10, 30, tzinfo=UTC)
    day = date(2026, 7, 10)

    assert _iter_values(None) == ()
    assert _iter_values("one") == ("one",)
    assert _iter_values(["one", "two"]) == ("one", "two")
    assert _iter_values(3) == (3,)
    assert _uuid(identifier) is identifier
    assert _uuid(str(identifier)) == identifier
    assert _optional_text(None) is None
    assert _optional_text(42) == "42"
    assert _date_text(None) is None
    assert _date_text(moment) == "2026-07-10"
    assert _date_text(day) == "2026-07-10"
    assert _date_text("2026-07-11") == "2026-07-11"
    assert _datetime(moment) is moment
    assert _datetime(moment.isoformat()) == moment

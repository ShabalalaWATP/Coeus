import json
import logging

from coeus.core.logging import JsonFormatter, configure_logging, get_logger


def test_json_formatter_includes_core_fields() -> None:
    record = logging.LogRecord(
        name="coeus.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-json"

    payload = json.loads(JsonFormatter().format(record))

    assert payload == {
        "level": "INFO",
        "logger": "coeus.test",
        "message": "hello",
        "request_id": "req-json",
    }


def test_json_formatter_includes_only_allowlisted_operational_fields() -> None:
    record = logging.LogRecord(
        name="coeus.outbox",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="outbox_dispatch_completed",
        args=(),
        exc_info=None,
    )
    record.claimed = 4
    record.delivered = 2
    record.failed = 2
    record.dead_lettered = 1
    record.payload = {"sensitive": "must-not-be-logged"}

    payload = json.loads(JsonFormatter().format(record))

    assert payload["claimed"] == 4
    assert payload["delivered"] == 2
    assert payload["failed"] == 2
    assert payload["dead_lettered"] == 1
    assert "payload" not in payload


def test_configure_logging_sets_root_level() -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        configure_logging("warning")

        assert root.level == logging.WARNING
        assert get_logger("coeus.sample").name == "coeus.sample"
    finally:
        root.handlers[:] = original_handlers
        root.setLevel(original_level)

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


def test_configure_logging_sets_root_level() -> None:
    configure_logging("warning")

    assert logging.getLogger().level == logging.WARNING
    assert get_logger("coeus.sample").name == "coeus.sample"

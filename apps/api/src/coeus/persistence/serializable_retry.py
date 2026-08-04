"""One bounded retry for a PostgreSQL serialisation failure."""

from collections.abc import Callable

from sqlalchemy.exc import OperationalError


def retry_serializable_once[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except OperationalError as error:
        if getattr(error.orig, "sqlstate", None) != "40001":
            raise
    return operation()

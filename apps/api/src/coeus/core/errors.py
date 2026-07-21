from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse

from coeus.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AppError(Exception):
    status_code: int
    code: str
    message: str


async def app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = str(getattr(request.state, "request_id", "unknown"))
    logger.exception(
        "unhandled_exception",
        extra={"request_id": request_id, "error": type(exc).__name__},
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred.",
                "request_id": request_id,
            }
        },
    )

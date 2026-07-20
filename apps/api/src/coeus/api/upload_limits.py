"""Receive-time request limits shared by multipart upload routes."""

from fastapi import Request
from starlette.types import Message, Receive

from coeus.core.errors import AppError


class UploadWireLimitExceeded(Exception):
    """The cumulative request body exceeded its receive-time budget."""


def install_receive_limit(request: Request, max_wire_bytes: int) -> None:
    """Reject oversized declared and streaming bodies before multipart spooling."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise AppError(400, "content_length_invalid", "Content-Length is invalid.") from exc
        if declared_length < 0:
            raise AppError(400, "content_length_invalid", "Content-Length is invalid.")
        if declared_length > max_wire_bytes:
            raise UploadWireLimitExceeded

    original_receive: Receive = request._receive
    received = 0

    async def limited_receive() -> Message:
        nonlocal received
        message = await original_receive()
        if message["type"] == "http.request":
            received += len(message.get("body", b""))
            if received > max_wire_bytes:
                raise UploadWireLimitExceeded
        return message

    request._receive = limited_receive

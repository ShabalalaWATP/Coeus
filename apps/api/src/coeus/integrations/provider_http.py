"""Shared synchronous JSON transport for key-based provider integrations."""

import json

import httpx


def get_json(url: str, *, headers: dict[str, str], timeout: int) -> object:
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


def post_json(
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, object],
    timeout: int,
    max_response_bytes: int,
) -> object:
    """Post JSON and reject oversized responses before buffering them fully."""
    if max_response_bytes < 1:
        raise ValueError("The provider response limit must be positive.")
    request_headers = {
        key: value for key, value in headers.items() if key.casefold() != "accept-encoding"
    }
    request_headers["Accept-Encoding"] = "identity"
    with (
        httpx.Client(timeout=timeout) as client,
        client.stream("POST", url, json=body, headers=request_headers) as response,
    ):
        response.raise_for_status()
        _validate_response_headers(response, max_response_bytes)
        content = bytearray()
        for chunk in response.iter_bytes():
            if len(content) + len(chunk) > max_response_bytes:
                raise ValueError("The provider response exceeded the allowed byte limit.")
            content.extend(chunk)
    return json.loads(content)


def _validate_response_headers(response: httpx.Response, max_response_bytes: int) -> None:
    """Reject encoded or declared-oversized bodies before decoded iteration."""
    response_headers = getattr(response, "headers", {})
    content_encoding = response_headers.get("content-encoding", "").strip().casefold()
    if content_encoding not in {"", "identity"}:
        raise ValueError("Encoded provider responses are not accepted.")
    declared_length = response_headers.get("content-length")
    if declared_length is None:
        return
    if not declared_length.isascii() or not declared_length.isdecimal():
        raise ValueError("The provider response length was invalid.")
    if int(declared_length) > max_response_bytes:
        raise ValueError("The provider response exceeded the allowed byte limit.")

"""Shared synchronous JSON transport for key-based provider integrations."""

import json

import httpx


def get_json(
    url: str,
    *,
    headers: dict[str, str],
    timeout: int,
    max_response_bytes: int,
) -> object:
    """Get JSON with the same bounded, uncompressed transport used for POST."""
    _require_response_limit(max_response_bytes)
    request_headers = _request_headers(headers)
    with (
        httpx.Client(timeout=timeout) as client,
        client.stream("GET", url, headers=request_headers) as response,
    ):
        return _read_json(response, max_response_bytes)


def post_json(
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, object],
    timeout: int,
    max_response_bytes: int,
) -> object:
    """Post JSON and reject oversized responses before buffering them fully."""
    _require_response_limit(max_response_bytes)
    request_headers = _request_headers(headers)
    with (
        httpx.Client(timeout=timeout) as client,
        client.stream("POST", url, json=body, headers=request_headers) as response,
    ):
        return _read_json(response, max_response_bytes)


def _request_headers(headers: dict[str, str]) -> dict[str, str]:
    bounded = {key: value for key, value in headers.items() if key.casefold() != "accept-encoding"}
    bounded["Accept-Encoding"] = "identity"
    return bounded


def _read_json(response: httpx.Response, max_response_bytes: int) -> object:
    response.raise_for_status()
    _validate_response_headers(response, max_response_bytes)
    content = bytearray()
    for chunk in response.iter_bytes():
        if len(content) + len(chunk) > max_response_bytes:
            raise ValueError("The provider response exceeded the allowed byte limit.")
        content.extend(chunk)
    return json.loads(content)


def _require_response_limit(max_response_bytes: int) -> None:
    if max_response_bytes < 1:
        raise ValueError("The provider response limit must be positive.")


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

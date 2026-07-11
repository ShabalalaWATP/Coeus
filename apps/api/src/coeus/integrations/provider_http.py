"""Shared synchronous JSON transport for key-based provider integrations."""

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
) -> object:
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=body, headers=headers)
        response.raise_for_status()
        return response.json()

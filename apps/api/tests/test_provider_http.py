"""Transport-level bounds for synchronous provider JSON calls."""

import pytest

from coeus.integrations.provider_http import get_json, post_json


class FakeResponse:
    def __init__(self, *, raw: bytes = b"{}", headers: dict[str, str] | None = None) -> None:
        self._raw = raw
        self.headers = headers or {}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self):  # type: ignore[no-untyped-def]
        yield self._raw


def _fake_client(response: FakeResponse, captured: dict[str, object]) -> type:
    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def stream(
            self,
            method: str,
            url: str,
            *,
            json: object | None = None,
            headers: dict[str, str],
        ) -> FakeResponse:
            captured["headers"] = headers
            return response

    return FakeClient


@pytest.mark.parametrize(
    ("headers", "message"),
    [
        ({"content-encoding": "gzip"}, "Encoded provider responses"),
        ({"content-encoding": "br"}, "Encoded provider responses"),
        ({"content-length": "11"}, "exceeded the allowed byte limit"),
        ({"content-length": "invalid"}, "response length was invalid"),
    ],
)
def test_response_headers_are_rejected_before_decoded_iteration(
    monkeypatch: pytest.MonkeyPatch,
    headers: dict[str, str],
    message: str,
) -> None:
    class RejectedResponse(FakeResponse):
        def iter_bytes(self):  # type: ignore[no-untyped-def]
            raise AssertionError("Rejected response body must not be decoded.")

    captured: dict[str, object] = {}
    response = RejectedResponse(headers=headers)
    monkeypatch.setattr(
        "coeus.integrations.provider_http.httpx.Client", _fake_client(response, captured)
    )

    with pytest.raises(ValueError, match=message):
        post_json(
            "https://provider.example.test",
            headers={},
            body={},
            timeout=1,
            max_response_bytes=10,
        )


def test_identity_response_with_bounded_declared_length_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    response = FakeResponse(headers={"content-encoding": "identity", "content-length": "2"})
    monkeypatch.setattr(
        "coeus.integrations.provider_http.httpx.Client", _fake_client(response, captured)
    )

    assert (
        post_json(
            "https://provider.example.test",
            headers={"accept-encoding": "gzip"},
            body={},
            timeout=1,
            max_response_bytes=2,
        )
        == {}
    )
    assert captured["headers"] == {"Accept-Encoding": "identity"}


def test_non_positive_transport_limit_is_rejected_before_network() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        post_json(
            "https://provider.example.test",
            headers={},
            body={},
            timeout=1,
            max_response_bytes=0,
        )


def test_get_json_uses_the_same_response_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    response = FakeResponse(raw=b'{"data":[]}', headers={"content-length": "11"})
    monkeypatch.setattr(
        "coeus.integrations.provider_http.httpx.Client", _fake_client(response, captured)
    )

    assert get_json(
        "https://provider.example.test/v1/models",
        headers={"Authorization": "Bearer test"},
        timeout=2,
        max_response_bytes=11,
    ) == {"data": []}
    assert captured["headers"] == {
        "Authorization": "Bearer test",
        "Accept-Encoding": "identity",
    }

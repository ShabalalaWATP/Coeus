import pytest
from starlette.responses import Response

from coeus.core.security import HSTS_HEADER, SECURITY_HEADERS, apply_security_headers


@pytest.mark.asyncio
async def test_security_headers_are_applied(api_client) -> None:
    response = await api_client.get("/api/v1/health/live")

    for header, expected_value in SECURITY_HEADERS.items():
        assert response.headers[header] == expected_value


@pytest.mark.asyncio
async def test_hsts_is_absent_over_plain_http(api_client) -> None:
    response = await api_client.get("/api/v1/health/live")

    assert HSTS_HEADER not in response.headers


def test_hsts_is_set_when_transport_is_secure() -> None:
    response = Response()

    apply_security_headers(response, secure_transport=True)

    assert response.headers[HSTS_HEADER] == "max-age=63072000; includeSubDomains"


def test_hsts_is_omitted_when_transport_is_insecure() -> None:
    response = Response()

    apply_security_headers(response, secure_transport=False)

    assert HSTS_HEADER not in response.headers

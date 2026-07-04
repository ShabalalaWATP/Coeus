import pytest

from coeus.core.security import SECURITY_HEADERS


@pytest.mark.asyncio
async def test_security_headers_are_applied(api_client) -> None:
    response = await api_client.get("/api/v1/health/live")

    for header, expected_value in SECURITY_HEADERS.items():
        assert response.headers[header] == expected_value

import pytest


@pytest.mark.asyncio
async def test_openapi_is_generated(api_client) -> None:
    response = await api_client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Istari API"
    assert "/api/v1/health/live" in schema["paths"]
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/auth/me" in schema["paths"]

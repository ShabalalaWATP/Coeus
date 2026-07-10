import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from coeus.core.errors import AppError, app_error_handler
from coeus.main import create_app


@pytest.mark.asyncio
async def test_app_error_handler_returns_stable_error_shape() -> None:
    app = create_app()

    @app.get("/raises-app-error")
    async def raises_app_error() -> None:
        raise AppError(status_code=409, code="conflict", message="Conflict detected.")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/raises-app-error")

    assert response.status_code == 409
    assert response.json() == {"error": {"code": "conflict", "message": "Conflict detected."}}


@pytest.mark.asyncio
async def test_unhandled_exception_handler_does_not_expose_details() -> None:
    app: FastAPI = create_app()

    @app.get("/raises-runtime-error")
    async def raises_runtime_error() -> None:
        raise RuntimeError("sensitive implementation detail")

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/raises-runtime-error", headers={"X-Request-ID": "req-123"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred.",
            "request_id": "req-123",
        }
    }


@pytest.mark.asyncio
async def test_app_error_handler_rejects_unexpected_exception_type() -> None:
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        httpx_request = client.build_request("GET", "/")
        request = Request(
            {
                "type": "http",
                "method": httpx_request.method,
                "path": str(httpx_request.url.path),
                "headers": list(httpx_request.headers.raw),
            }
        )

    with pytest.raises(RuntimeError, match="wrong handler"):
        await app_error_handler(request, RuntimeError("wrong handler"))

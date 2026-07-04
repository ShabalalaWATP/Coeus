from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.main import create_app


@pytest.fixture
async def api_client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

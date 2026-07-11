import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("COEUS_PERSISTENCE_PROVIDER", "memory")
# Tests assert exact queue/store contents; the rich demo dataset is opt-in per
# test (only test_demo_seed enables it) so every other suite sees the minimal
# deterministic seed.
os.environ.setdefault("COEUS_SEED_DEMO_CONTENT", "false")

from coeus.main import create_app


@pytest.fixture
async def api_client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

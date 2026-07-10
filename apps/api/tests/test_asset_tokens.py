import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import new as hmac_new
from typing import cast
from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.main import create_app
from coeus.services.asset_tokens import TOKEN_PREFIX, AssetTokenService, _b64


def test_asset_token_service_rejects_malformed_signed_claims() -> None:
    service = AssetTokenService("test-token-secret")
    admin = _admin_user()
    payload = {
        "asset_id": str(uuid4()),
        "break_glass": False,
        "exp": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "product_id": str(uuid4()),
        "user_id": str(admin.user_id),
    }

    with pytest.raises(AppError, match="asset_token_invalid"):
        service.verify(_signed_payload(service, payload | {"exp": "2099-01-01T00:00:00"}))
    with pytest.raises(AppError, match="asset_token_invalid"):
        service.verify(_signed_payload(service, payload | {"break_glass": "false"}))


def _admin_user() -> UserAccount:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    user = app.state.access_services.repository.get_user_by_username("admin@example.test")
    assert user is not None
    return cast(UserAccount, user)


def _signed_payload(service: AssetTokenService, payload: dict[str, object]) -> str:
    encoded = _b64(json.dumps(payload, sort_keys=True).encode("utf-8"))
    signature = _b64(hmac_new(service._secret, encoded.encode("ascii"), sha256).digest())
    return f"{TOKEN_PREFIX}{encoded}.{signature}"

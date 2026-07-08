import base64
import json
from binascii import Error as BinasciiError
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from hmac import new as hmac_new
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount

# Public token marker, not a secret.
TOKEN_PREFIX = "asset-token-"  # noqa: S105  # nosec B105


@dataclass(frozen=True)
class AssetTokenClaims:
    asset_id: UUID
    break_glass: bool
    expires_at: datetime
    product_id: UUID
    user_id: UUID


class AssetTokenService:
    def __init__(self, secret: str, ttl_seconds: int = 900) -> None:
        self._secret = secret.encode("utf-8")
        self._ttl_seconds = ttl_seconds

    def issue(
        self,
        actor: UserAccount,
        product_id: UUID,
        asset_id: UUID,
        *,
        break_glass: bool = False,
    ) -> str:
        expires_at = datetime.now(UTC) + timedelta(seconds=self._ttl_seconds)
        payload = {
            "asset_id": str(asset_id),
            "break_glass": break_glass,
            "exp": expires_at.isoformat(),
            "product_id": str(product_id),
            "user_id": str(actor.user_id),
        }
        encoded = _b64(json.dumps(payload, sort_keys=True).encode("utf-8"))
        signature = _b64(hmac_new(self._secret, encoded.encode("ascii"), sha256).digest())
        return f"{TOKEN_PREFIX}{encoded}.{signature}"

    def verify(self, token: str) -> AssetTokenClaims:
        if not token.startswith(TOKEN_PREFIX) or "." not in token:
            raise AppError(403, "asset_token_invalid", "Asset token is invalid.")
        encoded, signature = token.removeprefix(TOKEN_PREFIX).split(".", 1)
        expected = _b64(hmac_new(self._secret, encoded.encode("ascii"), sha256).digest())
        if not compare_digest(signature, expected):
            raise AppError(403, "asset_token_invalid", "Asset token is invalid.")
        try:
            payload = json.loads(_unb64(encoded).decode("utf-8"))
            expires_at = datetime.fromisoformat(str(payload["exp"]))
            asset_id = UUID(str(payload["asset_id"]))
            if expires_at.tzinfo is None or expires_at.utcoffset() is None:
                raise ValueError("Asset token expiry must include a timezone.")
            break_glass_claim = payload.get("break_glass", False)
            if not isinstance(break_glass_claim, bool):
                raise ValueError("Asset token break-glass claim must be boolean.")
            product_id = UUID(str(payload["product_id"]))
            user_id = UUID(str(payload["user_id"]))
        except (
            BinasciiError,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise AppError(403, "asset_token_invalid", "Asset token is invalid.") from exc
        if expires_at <= datetime.now(UTC):
            raise AppError(410, "asset_token_expired", "Asset token has expired.")
        return AssetTokenClaims(
            asset_id=asset_id,
            break_glass=break_glass_claim,
            expires_at=expires_at,
            product_id=product_id,
            user_id=user_id,
        )


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))

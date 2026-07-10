"""Generate or check the committed FastAPI OpenAPI contract."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
CONTRACT_PATH = ROOT / "packages" / "contracts" / "openapi.json"

if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))


def _configure_contract_environment(temp_dir: Path) -> None:
    os.environ["COEUS_ENVIRONMENT"] = "test"
    os.environ["COEUS_PERSISTENCE_PROVIDER"] = "memory"
    os.environ["COEUS_LOCAL_OBJECT_STORAGE_PATH"] = str(temp_dir / "objects")
    os.environ["COEUS_ARGON2_MEMORY_COST"] = "8192"
    os.environ["COEUS_CSRF_HEADER_NAME"] = "X-CSRF-Token"


def generate_contract() -> str:
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        _configure_contract_environment(temp_path)

        from coeus.core.config import Settings
        from coeus.main import create_app

        settings = Settings(
            environment="test",
            persistence_provider="memory",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(temp_path / "objects"),
        )
        schema = create_app(settings).openapi()
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the contract is stale")
    args = parser.parse_args()

    generated = generate_contract()
    if args.check:
        if not CONTRACT_PATH.exists():
            sys.stderr.write(f"{CONTRACT_PATH} is missing. Run pnpm contracts:generate.\n")
            return 1
        current = CONTRACT_PATH.read_text(encoding="utf-8")
        if current != generated:
            sys.stderr.write(f"{CONTRACT_PATH} is stale. Run pnpm contracts:generate.\n")
            return 1
        return 0

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(generated, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

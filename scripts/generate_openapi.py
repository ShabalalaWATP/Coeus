"""Generate or check the committed FastAPI OpenAPI contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
CONTRACT_PATH = ROOT / "packages" / "contracts" / "openapi.json"

if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from coeus.core.config import Settings  # noqa: E402
from coeus.main import create_app  # noqa: E402


def generate_contract() -> str:
    with TemporaryDirectory() as temp_dir:
        settings = Settings(
            environment="test",
            persistence_provider="memory",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(Path(temp_dir) / "objects"),
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

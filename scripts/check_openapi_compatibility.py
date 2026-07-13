"""Fail when the committed OpenAPI contract breaks a Git baseline."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
CONTRACT_PATH = ROOT / "packages" / "contracts" / "openapi.json"

if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from coeus.tools.openapi_compatibility import find_breaking_changes  # noqa: E402


def _load_json(data: str, label: str) -> dict[str, Any]:
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object.")
    return payload


def _baseline_from_git(reference: str) -> dict[str, Any]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required for OpenAPI compatibility checks.")
    result = subprocess.run(  # noqa: S603 - fixed git executable and repository path.
        [git, "show", f"{reference}:packages/contracts/openapi.json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return _load_json(result.stdout, reference)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="origin/main")
    parser.add_argument("--current", type=Path, default=CONTRACT_PATH)
    args = parser.parse_args()

    baseline = _baseline_from_git(args.baseline_ref)
    current = _load_json(args.current.read_text(encoding="utf-8"), str(args.current))
    changes = find_breaking_changes(baseline, current)
    if not changes:
        return 0
    sys.stderr.write("Breaking OpenAPI changes detected:\n")
    sys.stderr.writelines(f"- {change}\n" for change in changes)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

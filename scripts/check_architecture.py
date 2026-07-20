"""Fail when Python imports cross Coeus architecture boundaries."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps" / "api" / "src" / "coeus"

TEMPORARY_ALLOWLIST: frozenset[tuple[str, str]] = frozenset()
OBJECT_STORAGE_READ_OWNERS = frozenset(
    {
        "coeus.services.demo_seed",
        "coeus.services.qc_ingestion",
        "coeus.services.search_indexing",
        "coeus.services.workflow_draft_access",
    }
)


def module_name(path: Path) -> str:
    relative = path.relative_to(SOURCE.parent).with_suffix("")
    return ".".join(relative.parts)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.add(node.module)
    return imports


def forbidden(source: str, target: str) -> bool:
    if source.startswith("coeus.services."):
        return target == "fastapi" or target.startswith("fastapi.")
    if source.startswith("coeus.application."):
        return target.startswith(
            (
                "coeus.api",
                "coeus.integrations",
                "coeus.persistence",
                "coeus.repositories",
                "coeus.services",
            )
        )
    if source.startswith("coeus.domain."):
        return target.startswith(
            (
                "coeus.api",
                "coeus.persistence",
                "coeus.repositories",
                "coeus.services",
            )
        )
    if source.startswith(("coeus.persistence.", "coeus.repositories.")):
        return target.startswith(("coeus.api", "coeus.services"))
    return False


def violations() -> list[tuple[str, str, Path]]:
    found: list[tuple[str, str, Path]] = []
    for path in sorted(SOURCE.rglob("*.py")):
        source = module_name(path)
        content = path.read_text(encoding="utf-8")
        if source.startswith("coeus.services.") and "app.state" in content:
            found.append((source, "app.state", path))
        if (
            source.startswith("coeus.services.")
            and "storage.read_bytes(" in content
            and "object_storage.py" not in path.as_posix()
            and source not in OBJECT_STORAGE_READ_OWNERS
        ):
            found.append((source, "protected draft byte read", path))
        for target in sorted(imported_modules(path)):
            edge = (source, target)
            if forbidden(source, target) and edge not in TEMPORARY_ALLOWLIST:
                found.append((source, target, path))
    return found


def main() -> int:
    found = violations()
    if not found:
        print("Python architecture boundaries are clean.")
        return 0
    print("Forbidden Python architecture imports:", file=sys.stderr)
    for source, target, path in found:
        print(f"- {path.relative_to(ROOT)}: {source} -> {target}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

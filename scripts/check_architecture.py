"""Fail when Python imports cross Coeus architecture boundaries."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps" / "api" / "src" / "coeus"

TEMPORARY_ALLOWLIST: frozenset[tuple[str, str]] = frozenset()


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

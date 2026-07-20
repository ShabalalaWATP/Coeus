"""Reject unreferenced module-level Python declarations in application code.

This deliberately conservative check leaves decorated functions to their
frameworks and counts references by symbol name across the package. It is a
fast gate for obvious dead ends, not a substitute for coverage or review.
"""

from __future__ import annotations

import ast
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "apps" / "api" / "src" / "coeus"
REFERENCE_ROOTS = (SOURCE_ROOT, ROOT / "scripts")
INTENTIONAL_TEST_HARNESS = {
    ("services/search_evaluation.py", "evaluate_search_runs"),
}


@dataclass(frozen=True)
class Declaration:
    name: str
    path: Path
    line: int


class ReferenceCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.references: Counter[str] = Counter()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.references[node.id] += 1

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load):
            self.references[node.attr] += 1
        self.generic_visit(node)


def declarations(tree: ast.Module, path: Path) -> tuple[Declaration, ...]:
    found: list[Declaration] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        if node.name.startswith("_"):
            continue
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.decorator_list:
            continue
        found.append(Declaration(node.name, path, node.lineno))
    return tuple(found)


def main() -> int:
    references: Counter[str] = Counter()
    declared: list[Declaration] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        if "migrations" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        declared.extend(declarations(tree, path))
    for reference_root in REFERENCE_ROOTS:
        for path in reference_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            collector = ReferenceCollector()
            collector.visit(tree)
            references.update(collector.references)

    unused = [
        item
        for item in declared
        if references[item.name] == 0
        and (item.path.relative_to(SOURCE_ROOT).as_posix(), item.name)
        not in INTENTIONAL_TEST_HARNESS
    ]
    if unused:
        for item in unused:
            relative = item.path.relative_to(ROOT)
            sys.stderr.write(
                f"{relative}:{item.line}: unreferenced declaration {item.name}\n"
            )
        return 1
    sys.stdout.write("Python module-level declarations have application references.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

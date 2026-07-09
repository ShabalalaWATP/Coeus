from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ACTIVE_SOURCE_ROOTS = (
    ROOT / "apps" / "api" / "src" / "coeus" / "api",
    ROOT / "apps" / "api" / "src" / "coeus" / "domain",
    ROOT / "apps" / "api" / "src" / "coeus" / "integrations",
    ROOT / "apps" / "api" / "src" / "coeus" / "repositories",
    ROOT / "apps" / "api" / "src" / "coeus" / "schemas",
    ROOT / "apps" / "api" / "src" / "coeus" / "services",
    ROOT / "apps" / "web" / "src",
)
RETIRED_CONTRACT_TOKENS = (
    "/projects",
    "ProjectsPage",
    "projectId",
    "project_id",
    "project:",
    "suggestedProjectName",
)


def test_retired_workspace_contract_is_not_reintroduced() -> None:
    matches: list[str] = []

    for source_root in ACTIVE_SOURCE_ROOTS:
        for path in source_root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".ts", ".tsx"}:
                text = path.read_text(encoding="utf-8")
                matches.extend(
                    f"{path.relative_to(ROOT)} contains {token!r}"
                    for token in RETIRED_CONTRACT_TOKENS
                    if token in text
                )

    assert matches == []

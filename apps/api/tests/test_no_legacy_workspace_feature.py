from pathlib import Path

from coeus.core.config import Settings
from coeus.main import create_app

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
TEST_FILE_MARKERS = (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")


def test_retired_workspace_contract_is_not_reintroduced() -> None:
    matches: list[str] = []

    for source_root in ACTIVE_SOURCE_ROOTS:
        for path in source_root.rglob("*"):
            if (
                path.is_file()
                and path.suffix in {".py", ".ts", ".tsx"}
                and not path.name.endswith(TEST_FILE_MARKERS)
            ):
                text = path.read_text(encoding="utf-8")
                matches.extend(
                    f"{path.relative_to(ROOT)} contains {token!r}"
                    for token in RETIRED_CONTRACT_TOKENS
                    if token in text
                )

    assert matches == []


def test_retired_projects_api_route_is_not_registered() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/v1/projects" not in paths
    assert not any(path.startswith("/api/v1/projects/") for path in paths)

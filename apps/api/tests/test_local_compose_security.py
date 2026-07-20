import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_local_compose_published_ports_are_loopback_only() -> None:
    compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    published = [
        line.strip().removeprefix('- "').removesuffix('"')
        for line in compose.splitlines()
        if line.strip().startswith('- "') and line.strip().endswith('"')
    ]

    assert published
    assert all(str(port).startswith("127.0.0.1:") for port in published)


def test_api_container_starts_installed_server_without_uv_runtime_cache() -> None:
    dockerfile = (REPOSITORY_ROOT / "infra/docker/api.Dockerfile").read_text(encoding="utf-8")
    runtime_command = dockerfile[dockerfile.index("USER coeus") :]

    assert "uv run" not in runtime_command
    assert "exec /app/apps/api/.venv/bin/uvicorn" in runtime_command


def test_api_container_prepares_non_root_local_data_directory() -> None:
    dockerfile = (REPOSITORY_ROOT / "infra/docker/api.Dockerfile").read_text(encoding="utf-8")
    build_steps = dockerfile[: dockerfile.index("USER coeus")]

    assert "install -d -o coeus -g coeus /var/lib/coeus" in build_steps
    assert "chown -R coeus:coeus /app" not in build_steps


def test_runtime_pdf_dependency_is_available_in_production_image() -> None:
    configuration = tomllib.loads(
        (REPOSITORY_ROOT / "apps/api/pyproject.toml").read_text(encoding="utf-8")
    )

    assert any(
        dependency.startswith("reportlab")
        for dependency in configuration["project"]["dependencies"]
    )


def test_deployment_manifests_declare_jioc_routing_authority() -> None:
    compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    gcp_reference = (REPOSITORY_ROOT / "infra/gcp/environments/dev/main.tf").read_text(
        encoding="utf-8"
    )

    assert "COEUS_JIOC_AGENT_ROUTING_ENABLED: active" in compose
    assert "COEUS_JIOC_ROUTING_APPROVED_RELEASES:" in compose
    assert 'COEUS_JIOC_AGENT_ROUTING_ENABLED = "disabled"' in " ".join(gcp_reference.split())

from pathlib import Path


def test_local_compose_published_ports_are_loopback_only() -> None:
    compose = Path("../../docker-compose.yml").read_text(encoding="utf-8")
    published = [
        line.strip().removeprefix('- "').removesuffix('"')
        for line in compose.splitlines()
        if line.strip().startswith('- "') and line.strip().endswith('"')
    ]

    assert published
    assert all(str(port).startswith("127.0.0.1:") for port in published)

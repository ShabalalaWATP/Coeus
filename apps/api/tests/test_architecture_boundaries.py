from collections.abc import Callable
from pathlib import Path
from runpy import run_path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[3]
forbidden = cast(
    Callable[[str, str], bool],
    run_path(str(ROOT / "scripts" / "check_architecture.py"))["forbidden"],
)


@pytest.mark.parametrize(
    "source",
    (
        "coeus.services.jioc_routing_agent",
        "coeus.services.jioc_routing_context",
        "coeus.services.jioc_routing_policy",
        "coeus.services.routing_evaluation",
        "coeus.services.routing_review_updates",
    ),
)
def test_deterministic_routing_modules_cannot_import_provider_adapters(source: str) -> None:
    assert forbidden(source, "coeus.integrations.llm_gateway")


def test_non_authority_services_are_not_overblocked_from_provider_adapters() -> None:
    assert not forbidden("coeus.services.ticket_builder", "coeus.integrations.llm_gateway")

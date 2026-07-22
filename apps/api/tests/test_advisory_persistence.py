import json
from datetime import UTC, datetime
from uuid import uuid4

from coeus.domain.advisory_agents import (
    AdviceItemKind,
    AdvisoryAgentKind,
    AgentAdvice,
    AgentAdviceItem,
    AgentAdviceProvenance,
)
from coeus.domain.tickets import AgentRun, AgentRunStatus
from coeus.persistence.codec import decode_value, encode_value


def test_agent_run_bounded_advice_round_trips_without_prompt_or_raw_output() -> None:
    provenance = AgentAdviceProvenance(
        True,
        True,
        "provider_success",
        "synthetic-provider",
        "synthetic-model",
        12,
        "not_used",
        "passed",
        "search-planner-v1",
        "search-controller-v1",
        "search-context-v1",
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
        9,
        4,
    )
    advice = AgentAdvice(
        AdvisoryAgentKind.SEARCH_PLANNER,
        (
            AgentAdviceItem(
                AdviceItemKind.QUERY_EXPANSION,
                "harbour",
                "Synthetic harbour terminology.",
                ("title",),
            ),
        ),
        provenance,
    )
    run = AgentRun(
        uuid4(),
        uuid4(),
        "search-planner-agent",
        AgentRunStatus.COMPLETED,
        "Search suggestions validated.",
        (),
        datetime.now(UTC),
        advice=advice,
    )

    encoded = encode_value(run)

    assert decode_value(encoded) == run
    serialised = json.dumps(encoded)
    assert '"prompt":' not in serialised
    assert '"raw_output":' not in serialised

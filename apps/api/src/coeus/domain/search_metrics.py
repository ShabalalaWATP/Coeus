from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RfiSearchMetrics:
    run_id: UUID
    query: str
    candidate_count: int
    offered_count: int
    rejected_count: int
    accepted_product_id: UUID | None
    created_at: datetime
    retrieval_mode: str = "metadata_only"
    degraded_reason: str | None = None
    outcome: str = "incomplete"
    assurance: str = "assisted"
    coverage_status: str = "legacy"
    profile_space_id: str | None = None
    corpus_version: str | None = None

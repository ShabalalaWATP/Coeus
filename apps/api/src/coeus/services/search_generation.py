"""Decide when an active semantic generation remains safe to query."""


def semantic_generation_usable(index_status: str, degraded_reason: str | None) -> bool:
    """Allow corpus-stale vectors, but never cross provider or model generations."""
    return index_status == "ready" or (
        index_status == "stale" and degraded_reason == "corpus_changed"
    )

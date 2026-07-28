"""Tripwire for the grounded chunk index access predicates.

On the Postgres path `PostgresSearchIndexRepository.search` relies entirely
on the SQL `scoped` CTE for retrieval-time access control, so removing a
predicate there must fail a test.
"""

from coeus.persistence.search_index_sql import SEARCH_CHUNKS_SQL

_SCOPED, _AFTER_SCOPED = SEARCH_CHUNKS_SQL.split("), lexical AS", maxsplit=1)
_LEXICAL, _AFTER_LEXICAL = _AFTER_SCOPED.split("), semantic AS", maxsplit=1)
_SEMANTIC = _AFTER_LEXICAL.split("), selected AS", maxsplit=1)[0]


def test_scoped_cte_carries_every_access_predicate() -> None:
    assert "product.status = :published_status" in _SCOPED
    assert "product.classification_level <= :clearance_level" in _SCOPED
    assert "product.releasability = ARRAY['MOCK']::text[]" in _SCOPED
    assert "product.handling_caveats = ARRAY['MOCK DATA ONLY']::text[]" in _SCOPED
    assert "EXISTS" in _SCOPED
    assert "acg.acg_id = ANY(CAST(:acg_ids AS uuid[]))" in _SCOPED
    assert "profile.is_active" in _SCOPED


def test_both_retrieval_legs_read_only_from_the_scoped_cte() -> None:
    for leg in (_LEXICAL, _SEMANTIC):
        assert "FROM scoped" in leg
        assert "intelligence_store" not in leg
    assert "FROM scoped JOIN selected" in SEARCH_CHUNKS_SQL

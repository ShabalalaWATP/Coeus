INSERT_PROFILE_SQL = """
INSERT INTO search_index_profiles (
 profile_id, provider, model, dimensions, generation, space_id, status, is_active,
 corpus_version, product_count, chunk_count, indexed_count, failed_count,
 created_by_user_id, created_at, completed_at, error_code
) VALUES (
 CAST(:profile_id AS uuid), :provider, :model, :dimensions, :generation, :space_id,
 :status, :is_active, :corpus_version, :product_count, :chunk_count, :indexed_count,
 :failed_count, CAST(:created_by_user_id AS uuid), :created_at, :completed_at, :error_code
)
"""

UPSERT_CHUNK_SQL = """
INSERT INTO intelligence_store_search_chunks (
 chunk_id, product_id, asset_id, asset_name, asset_sha256, page_number, chunk_index,
 content, content_hash, extractor_version, chunker_version, search_document
) VALUES (
 CAST(:chunk_id AS uuid), CAST(:product_id AS uuid), CAST(:asset_id AS uuid), :asset_name,
 :asset_sha256, :page_number, :chunk_index, :content, :content_hash, :extractor_version,
 :chunker_version, to_tsvector('english', :content)
) ON CONFLICT (chunk_id) DO NOTHING
"""

INSERT_EMBEDDING_SQL = """
INSERT INTO intelligence_store_chunk_embeddings(profile_id, chunk_id, source_hash, embedding)
VALUES (CAST(:profile_id AS uuid), CAST(:chunk_id AS uuid), :source_hash,
        CAST(:embedding AS vector))
ON CONFLICT (profile_id, chunk_id) DO NOTHING
"""

UPSERT_TICKET_DOCUMENT_SQL = """
INSERT INTO ticket_search_documents(
 ticket_id, state, content, content_hash, search_document, updated_at
) VALUES (
 CAST(:ticket_id AS uuid), :state, :content, :content_hash,
 to_tsvector('english', :content), now()
) ON CONFLICT (ticket_id) DO UPDATE SET
 state = EXCLUDED.state, content = EXCLUDED.content,
 content_hash = EXCLUDED.content_hash, search_document = EXCLUDED.search_document,
 updated_at = CASE WHEN ticket_search_documents.content_hash <> EXCLUDED.content_hash
   THEN now() ELSE ticket_search_documents.updated_at END
"""

INSERT_TICKET_EMBEDDING_SQL = """
INSERT INTO ticket_search_embeddings(profile_id, ticket_id, source_hash, embedding)
VALUES (CAST(:profile_id AS uuid), CAST(:ticket_id AS uuid), :source_hash,
        CAST(:embedding AS vector))
ON CONFLICT (profile_id, ticket_id) DO NOTHING
"""

INSERT_ASSET_INDEX_STATE_SQL = """
INSERT INTO intelligence_store_asset_index_state(
 profile_id, product_id, asset_id, asset_sha256, status,
 page_count, chunk_count, error_code
) VALUES (
 CAST(:profile_id AS uuid), CAST(:product_id AS uuid), CAST(:asset_id AS uuid),
 :asset_sha256, :status, :page_count, :chunk_count, :error_code
)
ON CONFLICT (profile_id, asset_id) DO UPDATE SET
 status = EXCLUDED.status, page_count = EXCLUDED.page_count,
 chunk_count = EXCLUDED.chunk_count, error_code = EXCLUDED.error_code
"""

ACTIVATE_PROFILE_SQL = """
UPDATE search_index_profiles SET status = 'ready', is_active = true,
 product_count = :product_count, chunk_count = :chunk_count,
 indexed_count = :indexed_count, failed_count = :failed_count,
 completed_at = now(), error_code = NULL
WHERE profile_id = CAST(:profile_id AS uuid) AND status = 'indexing'
"""

SEARCH_CHUNKS_SQL = """
WITH scoped AS (
 SELECT c.*, e.embedding
 FROM intelligence_store_search_chunks c
 JOIN intelligence_store_chunk_embeddings e ON e.chunk_id = c.chunk_id
 JOIN search_index_profiles profile ON profile.profile_id = e.profile_id AND profile.is_active
 JOIN intelligence_store_products product ON product.product_id = c.product_id
 WHERE product.status = :published_status
   AND product.classification_level <= :clearance_level
   AND product.releasability = ARRAY['MOCK']::text[]
   AND product.handling_caveats = ARRAY['MOCK DATA ONLY']::text[]
   AND EXISTS (
     SELECT 1 FROM intelligence_store_product_acgs acg
     WHERE acg.product_id = product.product_id
       AND acg.acg_id = ANY(CAST(:acg_ids AS uuid[]))
   )
), lexical AS (
 SELECT chunk_id,
   ts_rank_cd(search_document, websearch_to_tsquery('english', :query)) lexical_score,
   row_number() OVER (ORDER BY ts_rank_cd(search_document,
     websearch_to_tsquery('english', :query)) DESC) lexical_rank
 FROM scoped WHERE :query IS NOT NULL
   AND search_document @@ websearch_to_tsquery('english', :query)
 ORDER BY lexical_score DESC LIMIT :leg_limit
), semantic AS (
 SELECT chunk_id, 1 - (embedding <=> CAST(:query_embedding AS vector)) vector_score,
   row_number() OVER (ORDER BY embedding <=> CAST(:query_embedding AS vector)) vector_rank
 FROM scoped WHERE CAST(:query_embedding AS text) IS NOT NULL
 ORDER BY embedding <=> CAST(:query_embedding AS vector) LIMIT :leg_limit
), selected AS (SELECT chunk_id FROM lexical UNION SELECT chunk_id FROM semantic)
SELECT scoped.chunk_id, scoped.product_id, scoped.asset_id, scoped.asset_name,
 scoped.page_number, scoped.content, lexical.lexical_score, lexical.lexical_rank,
 semantic.vector_score, semantic.vector_rank
FROM scoped JOIN selected USING (chunk_id)
LEFT JOIN lexical USING (chunk_id) LEFT JOIN semantic USING (chunk_id)
ORDER BY greatest(coalesce(lexical.lexical_score, 0), coalesce(semantic.vector_score, 0)) DESC
"""

SEARCH_TICKETS_SQL = """
WITH scoped AS (
 SELECT document.*, embedding.embedding
 FROM ticket_search_documents document
 JOIN ticket_search_embeddings embedding USING (ticket_id)
 JOIN search_index_profiles profile
   ON profile.profile_id = embedding.profile_id AND profile.is_active
 WHERE document.ticket_id = ANY(CAST(:ticket_ids AS uuid[]))
   AND document.state = ANY(CAST(:states AS text[]))
), lexical AS (
 SELECT ticket_id,
   ts_rank_cd(search_document, websearch_to_tsquery('english', :query)) lexical_score,
   row_number() OVER (ORDER BY ts_rank_cd(search_document,
     websearch_to_tsquery('english', :query)) DESC) lexical_rank
 FROM scoped WHERE :query IS NOT NULL
   AND search_document @@ websearch_to_tsquery('english', :query)
 ORDER BY lexical_score DESC LIMIT :leg_limit
), semantic AS (
 SELECT ticket_id, 1 - (embedding <=> CAST(:query_embedding AS vector)) vector_score,
   row_number() OVER (ORDER BY embedding <=> CAST(:query_embedding AS vector)) vector_rank
 FROM scoped WHERE CAST(:query_embedding AS text) IS NOT NULL
 ORDER BY embedding <=> CAST(:query_embedding AS vector) LIMIT :leg_limit
), selected AS (SELECT ticket_id FROM lexical UNION SELECT ticket_id FROM semantic)
SELECT scoped.ticket_id, lexical.lexical_score, lexical.lexical_rank,
 semantic.vector_score, semantic.vector_rank
FROM scoped JOIN selected USING (ticket_id)
LEFT JOIN lexical USING (ticket_id) LEFT JOIN semantic USING (ticket_id)
ORDER BY coalesce(1.0 / (60 + lexical.lexical_rank), 0)
       + coalesce(1.0 / (60 + semantic.vector_rank), 0) DESC,
 scoped.ticket_id
"""

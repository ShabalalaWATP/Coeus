"""Core durable tables included in coordinated logical recovery."""

from coeus.persistence.postgres_backup_table_spec import table as _table

CORE_TABLES = (
    _table("coeus_state", "namespace payload updated_at", "namespace"),
    _table(
        "coeus_audit_events",
        "event_id event_type occurred_at actor_user_id metadata",
        "occurred_at event_id",
    ),
    _table(
        "coeus_ticket_aggregates",
        "ticket_id requester_user_id state consumes_capacity version payload canonical_hash "
        "updated_at",
        "ticket_id",
    ),
    _table(
        "coeus_outbox",
        "event_id aggregate_id aggregate_version event_type payload created_at available_at "
        "attempt_count claimed_by claim_expires_at last_error delivered_at dead_lettered_at",
        "event_id",
    ),
    _table(
        "coeus_draft_audiences",
        "product_id principal_id reason ticket_id updated_at",
        "product_id principal_id reason ticket_id",
    ),
    _table(
        "intelligence_store_products",
        "product_id reference title summary description product_type source_type owner_team "
        "area_or_region classification_level releasability handling_caveats tags semantic_labels "
        "acg_ids status time_period_start time_period_end geojson_ref bounding_box "
        "created_by_user_id created_at updated_at search_document embedding embedding_source_hash",
        "product_id",
    ),
    _table(
        "intelligence_store_assets",
        "asset_id product_id name asset_type mime_type size_bytes sha256 object_key "
        "preview_kind created_at",
        "asset_id",
    ),
    _table("intelligence_store_product_acgs", "product_id acg_id", "product_id acg_id"),
    _table("intelligence_store_semantic_labels", "product_id label", "product_id label"),
)

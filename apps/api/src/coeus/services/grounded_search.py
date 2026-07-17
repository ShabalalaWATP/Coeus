from uuid import UUID

from coeus.domain.auth import UserAccount
from coeus.domain.search_index import GroundedSearchResult
from coeus.domain.store import StoreVisibilityScope, product_in_scope
from coeus.domain.tickets import IntakeDetails
from coeus.persistence.search_index_repository import SearchIndexRepository
from coeus.repositories.access import AccessRepository
from coeus.services.search_configuration import SearchConfigurationService
from coeus.services.search_embeddings import SearchEmbeddingService
from coeus.services.search_generation import semantic_generation_usable
from coeus.services.store import StoreServices


class GroundedSearchService:
    def __init__(
        self,
        index: SearchIndexRepository,
        configuration: SearchConfigurationService,
        embeddings: SearchEmbeddingService,
        store: StoreServices,
        access: AccessRepository,
    ) -> None:
        self._index = index
        self._configuration = configuration
        self._embeddings = embeddings
        self._store = store
        self._access = access

    def search(
        self,
        actor: UserAccount,
        intake: IntakeDetails,
        principal_id: UUID,
    ) -> GroundedSearchResult:
        state = self._configuration.state()
        query = weighted_query_text(intake)
        query_vector = (
            self._embeddings.embed(query, purpose="query", principal_id=principal_id)
            if semantic_generation_usable(state.index_status, state.degraded_reason)
            else None
        )
        scope = StoreVisibilityScope(
            acg_ids=self._access.active_acg_ids_for_user(actor.user_id),
            clearance_level=actor.clearance_level,
            include_drafts=False,
            draft_creator_user_id=actor.user_id,
            draft_principal_user_id=actor.user_id,
        )
        allowed = frozenset(
            product.product_id
            for product in self._store.repository.list_products()
            if product_in_scope(product, scope)
        )
        evidence = self._index.search(scope, query, query_vector, allowed)
        if state.chunk_count == 0:
            reason = (
                None
                if state.index_status == "stale" and state.changed_at is None
                else "index_unavailable"
            )
            return GroundedSearchResult(evidence, "metadata_only", reason, None)
        if query_vector is None:
            return GroundedSearchResult(
                evidence,
                "lexical_only",
                state.degraded_reason or f"index_{state.index_status}",
                None,
            )
        vector_used = any(item.vector_rank is not None for item in evidence)
        degraded_reason = (
            state.degraded_reason
            if vector_used and state.index_status == "stale"
            else None
            if vector_used
            else state.degraded_reason or "vector_no_candidates"
        )
        return GroundedSearchResult(
            evidence,
            "hybrid" if vector_used else "lexical_only",
            degraded_reason,
            state.space_id,
        )


def weighted_query_text(intake: IntakeDetails) -> str:
    groups = (
        ("need", intake.operational_question, intake.description),
        ("context", intake.known_context, intake.customer_success_criteria),
        ("scope", intake.area_or_region, intake.supported_operation),
        ("discipline", intake.intelligence_disciplines, intake.required_output_format),
        ("constraints", intake.requesting_unit, intake.restrictions_or_caveats),
        ("timing", intake.time_period_start, intake.time_period_end, intake.deadline),
        ("priority", intake.priority, intake.urgency_justification),
        ("title", intake.title),
    )
    return " | ".join(
        f"{label}: {' '.join(value for value in values if value)}"
        for label, *values in groups
        if any(values)
    )

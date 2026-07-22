"""Bounded, advisory-only outputs from the shadow routing critic."""

from dataclasses import dataclass
from enum import StrEnum


class RoutingCriticVerdict(StrEnum):
    SUPPORTS = "supports"
    CHALLENGES = "challenges"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNAVAILABLE = "unavailable"


class RoutingCriticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"


class RoutingChallengeCode(StrEnum):
    TICKET_ID_MISMATCH = "ticket_id_mismatch"
    CONTEXT_ID_MISMATCH = "context_id_mismatch"
    CONTEXT_SCHEMA_MISMATCH = "context_schema_mismatch"
    ROUTING_RELEASE_MISMATCH = "routing_release_mismatch"
    SEARCH_OFFER_INCONSISTENT = "search_offer_inconsistent"
    ACTIVE_WORK_OFFER_INCONSISTENT = "active_work_offer_inconsistent"
    CAPACITY_ENTRY_MALFORMED = "capacity_entry_malformed"
    CAPACITY_ENTRY_DUPLICATED = "capacity_entry_duplicated"
    CAPACITY_SNAPSHOT_STALE = "capacity_snapshot_stale"
    ROUTE_REVIEW_INCONSISTENT = "route_review_inconsistent"
    DISPOSITION_ROUTE_INCONSISTENT = "disposition_route_inconsistent"
    EVIDENCE_OUTCOME_INCONSISTENT = "evidence_outcome_inconsistent"
    COMMITTED_STATE_INCONSISTENT = "committed_state_inconsistent"


class RoutingMissingEvidenceCode(StrEnum):
    SEARCH_ASSURANCE = "search_assurance_missing"
    SEARCH_CORPUS_VERSION = "search_corpus_version_missing"
    PRODUCT_OFFER_RESOLUTION = "product_offer_resolution_missing"
    ACTIVE_WORK_SEARCH = "active_work_search_missing"
    ACTIVE_WORK_OFFER_RESOLUTION = "active_work_offer_resolution_missing"
    CAPABILITY_CATALOGUE = "capability_catalogue_missing"
    AVAILABILITY_SNAPSHOT = "availability_snapshot_missing"
    CANDIDATE_CAPACITY = "candidate_capacity_missing"
    ROUTE_REVIEW_SUPPORT = "route_review_support_missing"


class RoutingFactId(StrEnum):
    RECORD_IDENTITIES = "record_identities"
    CONTEXT_SCHEMA = "context_schema"
    ROUTING_RELEASE = "routing_release"
    SEARCH_STATUS = "search_status"
    PRODUCT_OFFERS = "product_offers"
    ACTIVE_WORK_STATUS = "active_work_status"
    ACTIVE_WORK_OFFERS = "active_work_offers"
    CAPABILITY_CATALOGUE = "capability_catalogue"
    AVAILABILITY_SNAPSHOT = "availability_snapshot"
    CANDIDATE_CAPACITY = "candidate_capacity"
    CAPABILITY_REVIEWS = "capability_reviews"
    ROUTING_DECISION = "routing_decision"
    COMMITTED_STATE = "committed_state"


class RoutingReviewQuestionCode(StrEnum):
    VERIFY_RECORD_LINKAGE = "verify_record_linkage"
    VERIFY_RELEASE_COMPATIBILITY = "verify_release_compatibility"
    RERUN_PRODUCT_SEARCH = "rerun_product_search"
    RESOLVE_PRODUCT_OFFERS = "resolve_product_offers"
    RERUN_ACTIVE_WORK_SEARCH = "rerun_active_work_search"
    RESOLVE_ACTIVE_WORK_OFFERS = "resolve_active_work_offers"
    REFRESH_CAPACITY_SNAPSHOT = "refresh_capacity_snapshot"
    VERIFY_CAPACITY_RECORDS = "verify_capacity_records"
    RECONCILE_ROUTE_EVIDENCE = "reconcile_route_evidence"
    RETURN_TO_JIOC_REVIEW = "return_to_jioc_review"


@dataclass(frozen=True)
class RoutingCritiqueDraft:
    """Normalised criticism with no workflow-control fields."""

    verdict: RoutingCriticVerdict
    severity: RoutingCriticSeverity
    challenge_codes: tuple[RoutingChallengeCode, ...] = ()
    missing_evidence_codes: tuple[RoutingMissingEvidenceCode, ...] = ()
    cited_fact_ids: tuple[RoutingFactId, ...] = ()
    review_question_codes: tuple[RoutingReviewQuestionCode, ...] = ()

from dataclasses import replace
from uuid import uuid4

from coeus.domain.access import ProductStatus
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.store import StoreProduct, StoreVisibilityScope, product_in_scope
from store_projection_helpers import seed_product


def test_ticket_state_machine_allows_defined_transition() -> None:
    assert can_transition(TicketState.DRAFT_INTAKE, TicketState.RFI_SEARCHING) is True


def test_legacy_no_match_state_uses_unified_customer_decision_exits() -> None:
    allowed = {target for target in TicketState if can_transition(TicketState.RFI_NO_MATCH, target)}

    assert allowed == {TicketState.JIOC_ROUTING_PENDING, TicketState.CLOSED_UNANSWERED}


def test_incomplete_search_cannot_advance_to_routing() -> None:
    allowed = {
        target
        for target in TicketState
        if can_transition(TicketState.RFI_SEARCH_INCOMPLETE, target)
    }

    assert allowed == {
        TicketState.RFI_MATCH_OFFERED,
        TicketState.NEW_TASKING_CONSENT,
        TicketState.CANCELLED,
    }


def test_legacy_state_values_decode_to_jioc_review() -> None:
    assert TicketState("ROUTE_ASSESSMENT") is TicketState.JIOC_REVIEW
    assert TicketState("RFA_MANAGER_REVIEW") is TicketState.JIOC_REVIEW
    assert TicketState("CM_MANAGER_REVIEW") is TicketState.JIOC_REVIEW
    # Tickets awaiting the retired manager-release step return to QC.
    assert TicketState("MANAGER_RELEASE") is TicketState.QC_REVIEW


def test_analyst_work_now_routes_through_manager_approval() -> None:
    assert can_transition(TicketState.ANALYST_IN_PROGRESS, TicketState.MANAGER_APPROVAL) is True
    assert can_transition(TicketState.ANALYST_IN_PROGRESS, TicketState.QC_REVIEW) is False
    assert can_transition(TicketState.MANAGER_APPROVAL, TicketState.QC_REVIEW) is True
    assert can_transition(TicketState.MANAGER_APPROVAL, TicketState.ANALYST_IN_PROGRESS) is True
    # QC either releases or forwards an analysed collect back to assignment.
    assert can_transition(TicketState.QC_REVIEW, TicketState.DISSEMINATION_READY) is True
    assert can_transition(TicketState.QC_REVIEW, TicketState.ANALYST_ASSIGNMENT) is True


def test_ticket_state_machine_denies_undefined_transition() -> None:
    assert can_transition(TicketState.CANCELLED, TicketState.DRAFT_INTAKE) is False


def _published() -> StoreProduct:
    base = seed_product()
    metadata = replace(base.metadata, status=ProductStatus.PUBLISHED, classification_level=2)
    return replace(base, metadata=metadata)


def test_product_in_scope_allows_permitted_product() -> None:
    product = _published()
    scope = StoreVisibilityScope(
        acg_ids=product.metadata.acg_ids, clearance_level=3, include_drafts=False
    )

    assert product_in_scope(product, scope) is True


def test_product_in_scope_blocks_over_clearance_and_foreign_acg_and_archived() -> None:
    product = _published()
    over_clearance = StoreVisibilityScope(
        acg_ids=product.metadata.acg_ids, clearance_level=1, include_drafts=False
    )
    foreign_acg = StoreVisibilityScope(
        acg_ids=frozenset({uuid4()}), clearance_level=5, include_drafts=False
    )
    full_scope = StoreVisibilityScope(
        acg_ids=product.metadata.acg_ids, clearance_level=5, include_drafts=True
    )
    archived = replace(product, metadata=replace(product.metadata, status=ProductStatus.ARCHIVED))

    assert product_in_scope(product, over_clearance) is False
    assert product_in_scope(product, foreign_acg) is False
    assert product_in_scope(archived, full_scope) is False


def test_product_in_scope_hides_drafts_unless_included() -> None:
    product = _published()
    draft = replace(product, metadata=replace(product.metadata, status=ProductStatus.DRAFT))
    without_drafts = StoreVisibilityScope(
        acg_ids=product.metadata.acg_ids, clearance_level=5, include_drafts=False
    )
    with_drafts = replace(without_drafts, include_drafts=True)

    assert product_in_scope(draft, without_drafts) is False
    assert product_in_scope(draft, with_drafts) is True

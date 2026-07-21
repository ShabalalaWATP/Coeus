"""Durable, identifier-only request for post-commit routing criticism."""

from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import JiocRoutingContext, JiocRoutingDecision
from coeus.domain.tickets import CmCapabilityReview, RfaCapabilityReview
from coeus.domain.workflow_transaction import WorkflowOutboxIntent

ROUTING_CRITIQUE_REQUESTED = "jioc_routing_critique_requested"


def routing_critique_intent(
    context: JiocRoutingContext,
    decision: JiocRoutingDecision,
    rfa: RfaCapabilityReview,
    cm: CmCapabilityReview,
    committed_state: TicketState,
) -> WorkflowOutboxIntent:
    return WorkflowOutboxIntent(
        ROUTING_CRITIQUE_REQUESTED,
        {
            "decision_id": str(decision.decision_id),
            "context_id": str(context.context_id),
            "rfa_review_id": str(rfa.review_id),
            "cm_review_id": str(cm.review_id),
            "committed_state": committed_state.value,
        },
    )

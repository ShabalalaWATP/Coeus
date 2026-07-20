"""Stable and legacy identities accepted by the persistence codec."""

from collections.abc import Mapping, Sequence
from typing import Any

from coeus.core.permissions import Permission
from coeus.domain.access import (
    AccessCheck,
    AccessControlGroup,
    AccessControlGroupMembership,
    AccessDecision,
    AcgAccessApplication,
    AcgApplicationStatus,
    ProductRecord,
    ProductStatus,
)
from coeus.domain.auth import RoleName, SessionRecord, UserAccount
from coeus.domain.capabilities import CandidateTeam
from coeus.domain.customer_outcomes import (
    CustomerProductDecision,
    CustomerProductDecisionStatus,
    JiocReanalysisDecision,
    JiocReanalysisStatus,
    ManagerReanalysisDecision,
    ManagerReanalysisStatus,
    ProductOutcomeHistory,
)
from coeus.domain.enums import TicketState
from coeus.domain.jioc_intervention import JiocIntervention
from coeus.domain.jioc_routing import JiocRoutingContext, JiocRoutingDecision
from coeus.domain.notifications import EmailRecord, NotificationRecord
from coeus.domain.prioritisation import PriorityAssessment
from coeus.domain.product_submission import DraftProductAsset, DraftProductVersion
from coeus.domain.qc import (
    FeedbackRequest,
    FeedbackRequestStatus,
    FeedbackSubmission,
    ProductIndexRecord,
    ProductIndexStatus,
    QcAgentCheck,
    QcAgentFinding,
    QcAgentPreflight,
    QcAgentPreflightStatus,
    QcChecklistItem,
    QcDecision,
    QcDecisionStatus,
)
from coeus.domain.registration import RegistrationRequest, RegistrationStatus
from coeus.domain.search_index import GroundedProductEvidence, SearchPassage
from coeus.domain.search_metrics import RfiSearchMetrics
from coeus.domain.store import BoundingBox, StoreAsset, StoreProduct, StoreProductMetadata
from coeus.domain.teams import CalendarStatus, OrgTeam, TeamCalendarEntry, TeamKind, UserProfile
from coeus.domain.tickets import (
    AgentRun,
    AgentRunStatus,
    AnalystAssignment,
    AnalystNote,
    AnalystWorkPackage,
    AttachmentMetadata,
    ChatMessage,
    ClarificationRequest,
    CmCapabilityReview,
    CollaboratorAccess,
    IntakeDetails,
    LinkedAnalystProduct,
    ManagerRoutingDecision,
    ManagerRoutingDecisionStatus,
    MessageAuthor,
    ProductDissemination,
    ProductOffer,
    ProductOfferStatus,
    RfaCapabilityReview,
    RouteRecommendation,
    RoutingRoute,
    TicketCollaborator,
    TicketRecord,
    TicketTimelineEntry,
    WorkflowPlanUpdate,
    WorkPackageStatus,
)
from coeus.domain.work_discovery import ActiveWorkOffer

CodecClass = type[Any]
CodecIdentity = tuple[CodecClass, str]

# Reader-only aliases preserve rows written before a class moved modules. New
# writes always use the stable semantic identity declared in TYPE_IDENTITIES.
LEGACY_TYPE_ALIASES: Mapping[str, CodecClass] = {
    "coeus.domain.tickets.RfiSearchMetrics": RfiSearchMetrics,
    "coeus.domain.tickets.DraftProductAsset": DraftProductAsset,
    "coeus.domain.tickets.DraftProductVersion": DraftProductVersion,
}

TYPE_IDENTITIES: tuple[CodecIdentity, ...] = (
    (AcgAccessApplication, "access.acg_access_application"),
    (AccessCheck, "access.access_check"),
    (AccessControlGroup, "access.access_control_group"),
    (AccessControlGroupMembership, "access.access_control_group_membership"),
    (AccessDecision, "access.access_decision"),
    (ProductRecord, "access.product_record"),
    (SessionRecord, "auth.session_record"),
    (UserAccount, "auth.user_account"),
    (CandidateTeam, "capabilities.candidate_team"),
    (CustomerProductDecision, "customer_outcomes.customer_product_decision"),
    (ManagerReanalysisDecision, "customer_outcomes.manager_reanalysis_decision"),
    (JiocReanalysisDecision, "customer_outcomes.jioc_reanalysis_decision"),
    (ProductOutcomeHistory, "customer_outcomes.product_outcome_history"),
    (EmailRecord, "notifications.email_record"),
    (NotificationRecord, "notifications.notification_record"),
    (PriorityAssessment, "prioritisation.priority_assessment"),
    (FeedbackRequest, "qc.feedback_request"),
    (FeedbackSubmission, "qc.feedback_submission"),
    (ProductIndexRecord, "qc.product_index_record"),
    (QcAgentCheck, "qc.qc_agent_check"),
    (QcAgentFinding, "qc.qc_agent_finding"),
    (QcAgentPreflight, "qc.qc_agent_preflight"),
    (QcChecklistItem, "qc.qc_checklist_item"),
    (QcDecision, "qc.qc_decision"),
    (RegistrationRequest, "registration.registration_request"),
    (BoundingBox, "store.bounding_box"),
    (StoreAsset, "store.asset"),
    (StoreProduct, "store.product"),
    (StoreProductMetadata, "store.product_metadata"),
    (OrgTeam, "teams.org_team"),
    (TeamCalendarEntry, "teams.calendar_entry"),
    (UserProfile, "teams.user_profile"),
    (AgentRun, "tickets.agent_run"),
    (ActiveWorkOffer, "tickets.active_work_offer"),
    (JiocRoutingContext, "tickets.jioc_routing_context"),
    (JiocRoutingDecision, "tickets.jioc_routing_decision"),
    (JiocIntervention, "tickets.jioc_intervention"),
    (AnalystAssignment, "tickets.analyst_assignment"),
    (AnalystNote, "tickets.analyst_note"),
    (AnalystWorkPackage, "tickets.analyst_work_package"),
    (AttachmentMetadata, "tickets.attachment_metadata"),
    (ChatMessage, "tickets.chat_message"),
    (ClarificationRequest, "tickets.clarification_request"),
    (CmCapabilityReview, "tickets.cm_capability_review"),
    (DraftProductAsset, "tickets.draft_product_asset"),
    (DraftProductVersion, "tickets.draft_product_version"),
    (IntakeDetails, "tickets.intake_details"),
    (LinkedAnalystProduct, "tickets.linked_analyst_product"),
    (ManagerRoutingDecision, "tickets.manager_routing_decision"),
    (ProductDissemination, "tickets.product_dissemination"),
    (ProductOffer, "tickets.product_offer"),
    (GroundedProductEvidence, "tickets.grounded_product_evidence"),
    (RfaCapabilityReview, "tickets.rfa_capability_review"),
    (RfiSearchMetrics, "tickets.rfi_search_metrics"),
    (SearchPassage, "tickets.search_passage"),
    (RouteRecommendation, "tickets.route_recommendation"),
    (TicketCollaborator, "tickets.ticket_collaborator"),
    (TicketRecord, "tickets.ticket_record"),
    (TicketTimelineEntry, "tickets.ticket_timeline_entry"),
    (WorkflowPlanUpdate, "tickets.workflow_plan_update"),
)

ENUM_IDENTITIES: tuple[CodecIdentity, ...] = (
    (AcgApplicationStatus, "access.acg_application_status"),
    (ProductStatus, "access.product_status"),
    (RoleName, "auth.role_name"),
    (Permission, "core.permission"),
    (FeedbackRequestStatus, "qc.feedback_request_status"),
    (ProductIndexStatus, "qc.product_index_status"),
    (QcAgentPreflightStatus, "qc.qc_agent_preflight_status"),
    (QcDecisionStatus, "qc.qc_decision_status"),
    (RegistrationStatus, "registration.registration_status"),
    (CalendarStatus, "teams.calendar_status"),
    (TeamKind, "teams.team_kind"),
    (AgentRunStatus, "tickets.agent_run_status"),
    (CollaboratorAccess, "tickets.collaborator_access"),
    (ManagerRoutingDecisionStatus, "tickets.manager_routing_decision_status"),
    (MessageAuthor, "tickets.message_author"),
    (ProductOfferStatus, "tickets.product_offer_status"),
    (RoutingRoute, "tickets.routing_route"),
    (TicketState, "tickets.ticket_state"),
    (WorkPackageStatus, "tickets.work_package_status"),
    (CustomerProductDecisionStatus, "customer_outcomes.customer_product_decision_status"),
    (ManagerReanalysisStatus, "customer_outcomes.manager_reanalysis_status"),
    (JiocReanalysisStatus, "customer_outcomes.jioc_reanalysis_status"),
)


def build_identity_registries(
    identities: Sequence[CodecIdentity],
) -> tuple[Mapping[CodecClass, str], Mapping[str, CodecClass], Mapping[str, CodecClass]]:
    """Build stable writer, stable reader and legacy reader registries."""

    by_type: dict[CodecClass, str] = {}
    stable: dict[str, CodecClass] = {}
    legacy: dict[str, CodecClass] = {}
    for python_type, stable_id in identities:
        legacy_id = f"{python_type.__module__}.{python_type.__name__}"
        if python_type in by_type or stable_id in stable or legacy_id in legacy:
            raise RuntimeError("Persistence codec identities must be unique.")
        by_type[python_type] = stable_id
        stable[stable_id] = python_type
        legacy[legacy_id] = python_type
    return by_type, stable, legacy

from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID

from coeus.core.permissions import Permission
from coeus.domain.access import (
    AccessCheck,
    AccessControlGroup,
    AccessControlGroupMembership,
    AccessDecision,
    ProductRecord,
    ProductStatus,
)
from coeus.domain.auth import RoleName, SessionRecord, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.notifications import EmailRecord, NotificationRecord
from coeus.domain.qc import (
    FeedbackRequest,
    FeedbackRequestStatus,
    FeedbackSubmission,
    ProductIndexRecord,
    ProductIndexStatus,
    QcChecklistItem,
    QcDecision,
    QcDecisionStatus,
)
from coeus.domain.registration import RegistrationRequest, RegistrationStatus
from coeus.domain.store import BoundingBox, StoreAsset, StoreProduct, StoreProductMetadata
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
    DraftProductAsset,
    DraftProductVersion,
    IntakeDetails,
    LinkedAnalystProduct,
    ManagerRoutingDecision,
    ManagerRoutingDecisionStatus,
    MessageAuthor,
    ProductDissemination,
    ProductOffer,
    ProductOfferStatus,
    RfaCapabilityReview,
    RfiSearchMetrics,
    RouteRecommendation,
    RoutingRoute,
    TicketCollaborator,
    TicketRecord,
    TicketTimelineEntry,
    WorkflowPlanUpdate,
    WorkPackageStatus,
)

_ALLOWED_TYPES = (
    AccessCheck,
    AccessControlGroup,
    AccessControlGroupMembership,
    AccessDecision,
    AgentRun,
    AnalystAssignment,
    AnalystNote,
    AnalystWorkPackage,
    AttachmentMetadata,
    BoundingBox,
    ChatMessage,
    ClarificationRequest,
    CmCapabilityReview,
    DraftProductAsset,
    DraftProductVersion,
    EmailRecord,
    FeedbackRequest,
    FeedbackSubmission,
    IntakeDetails,
    LinkedAnalystProduct,
    ManagerRoutingDecision,
    NotificationRecord,
    ProductDissemination,
    ProductIndexRecord,
    ProductOffer,
    ProductRecord,
    QcChecklistItem,
    QcDecision,
    RegistrationRequest,
    RfaCapabilityReview,
    RfiSearchMetrics,
    RouteRecommendation,
    SessionRecord,
    StoreAsset,
    StoreProduct,
    StoreProductMetadata,
    TicketCollaborator,
    TicketRecord,
    TicketTimelineEntry,
    UserAccount,
    WorkflowPlanUpdate,
)

_ALLOWED_ENUMS = (
    AgentRunStatus,
    CollaboratorAccess,
    FeedbackRequestStatus,
    ManagerRoutingDecisionStatus,
    MessageAuthor,
    Permission,
    ProductStatus,
    ProductIndexStatus,
    ProductOfferStatus,
    QcDecisionStatus,
    RegistrationStatus,
    RoleName,
    RoutingRoute,
    TicketState,
    WorkPackageStatus,
)

_TYPE_REGISTRY = {f"{item.__module__}.{item.__name__}": item for item in _ALLOWED_TYPES}
_ENUM_REGISTRY = {f"{item.__module__}.{item.__name__}": item for item in _ALLOWED_ENUMS}


def encode_value(value: Any) -> Any:
    if is_dataclass(value):
        return {
            "__type__": f"{value.__class__.__module__}.{value.__class__.__name__}",
            "fields": {
                field.name: encode_value(getattr(value, field.name)) for field in fields(value)
            },
        }
    if isinstance(value, StrEnum):
        return {
            "__enum__": f"{value.__class__.__module__}.{value.__class__.__name__}",
            "value": value.value,
        }
    if isinstance(value, UUID):
        return {"__uuid__": str(value)}
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, frozenset):
        return {"__frozenset__": [encode_value(item) for item in sorted(value, key=str)]}
    if isinstance(value, tuple):
        return {"__tuple__": [encode_value(item) for item in value]}
    if isinstance(value, MappingProxyType):
        return {"__mapping__": {key: encode_value(item) for key, item in value.items()}}
    if isinstance(value, dict):
        return {str(key): encode_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode_value(item) for item in value]
    return value


def decode_value(value: Any) -> Any:
    if isinstance(value, list):
        return _decode_items(value)
    if not isinstance(value, dict):
        return value
    if "__uuid__" in value:
        return UUID(value["__uuid__"])
    if "__datetime__" in value:
        return datetime.fromisoformat(value["__datetime__"])
    if "__frozenset__" in value:
        return frozenset(_decode_items(value["__frozenset__"]))
    if "__tuple__" in value:
        return tuple(_decode_items(value["__tuple__"]))
    if "__mapping__" in value:
        return MappingProxyType(_decode_mapping(value["__mapping__"]))
    if "__enum__" in value:
        enum_type = _ENUM_REGISTRY[value["__enum__"]]
        return enum_type(value["value"])
    if "__type__" in value:
        data_type = _TYPE_REGISTRY[value["__type__"]]
        field_names = {field.name for field in fields(data_type)}
        raw_fields = dict(value["fields"])
        decoded = _decode_mapping(
            {key: item for key, item in raw_fields.items() if key in field_names}
        )
        return data_type(**decoded)
    return _decode_mapping(value)


def _decode_items(values: list[Any]) -> list[Any]:
    return [decode_value(item) for item in values]


def _decode_mapping(value: dict[Any, Any]) -> dict[str, Any]:
    return {str(key): decode_value(item) for key, item in value.items()}

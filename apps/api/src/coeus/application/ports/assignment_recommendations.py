"""Persistence boundary for deterministic assignment recommendations."""

from typing import Protocol
from uuid import UUID

from coeus.domain.assignment_recommendations import (
    AcceptRecommendationRequest,
    AssignmentRecommendationAcceptance,
    AssignmentRecommendationPreview,
    PrepareRecommendationRequest,
)


class AssignmentRecommendationStore(Protocol):
    def prepare(
        self, actor_user_id: UUID, request: PrepareRecommendationRequest
    ) -> AssignmentRecommendationPreview: ...

    def acceptance(
        self, actor_user_id: UUID, request: AcceptRecommendationRequest
    ) -> AssignmentRecommendationAcceptance: ...

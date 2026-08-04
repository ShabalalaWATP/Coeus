"""Dependency boundary for management-only assignment recommendations."""

from fastapi import Request

from coeus.core.errors import AppError
from coeus.services.assignment_recommendations import AssignmentRecommendationService


def get_assignment_recommendation_service(request: Request) -> AssignmentRecommendationService:
    service = getattr(request.app.state, "assignment_recommendation_service", None)
    if not isinstance(service, AssignmentRecommendationService):
        raise AppError(
            503,
            "assignment_recommendation_unavailable",
            "Assignment recommendations are not available in this operating mode.",
        )
    return service

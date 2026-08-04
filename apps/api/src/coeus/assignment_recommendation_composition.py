"""Management-only assignment recommendation composition."""

from fastapi import FastAPI

from coeus.services.assignment_recommendations import AssignmentRecommendationService


def configure_assignment_recommendations(app: FastAPI) -> None:
    administration = app.state.organisation_administration
    app.state.assignment_recommendation_service = (
        AssignmentRecommendationService(
            app.state.ticket_services,
            app.state.analyst_assignment_service,
            administration.assignment_recommendations,
        )
        if administration is not None
        else None
    )

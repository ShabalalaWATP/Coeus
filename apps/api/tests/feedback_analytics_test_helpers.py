from typing import cast
from uuid import UUID

from fastapi import FastAPI

from coeus.core.config import Settings
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app


def approval_payload(acg_id: str) -> dict[str, object]:
    return {
        "checklist": {
            "answers_customer_question": True,
            "sources_are_sufficient": True,
            "metadata_complete": True,
            "classification_checked": True,
            "releasability_checked": True,
            "acg_assignment_checked": True,
            "format_correct": True,
            "handling_caveats_applied": True,
            "manager_comments_resolved": True,
        },
        "classificationLevel": 2,
        "releasability": ["MOCK"],
        "handlingCaveats": ["MOCK DATA ONLY"],
        "acgIds": [acg_id],
        "reason": "QC checklist complete.",
    }


def legacy_routing_app() -> FastAPI:
    return create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            automatic_request_discovery_enabled=False,
        )
    )


def draft_payload() -> dict[str, object]:
    return {
        "title": "Arctic feedback product",
        "summary": "MOCK DATA ONLY analyst product draft.",
        "productType": "finished_output",
        "content": "MOCK DATA ONLY. Assessment content prepared for feedback analytics.",
        "assets": [
            {
                "name": "feedback-draft.pdf",
                "assetType": "pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 512,
                "sha256": "d" * 64,
            }
        ],
    }


def acg_id(app: FastAPI, code: str) -> str:
    for acg in app.state.access_services.repository.list_acgs():
        if acg.code == code:
            return str(acg.acg_id)
    raise AssertionError(f"Missing seed ACG {code}")


def ticket_for_feedback_request(app: FastAPI, request_id: str) -> TicketRecord:
    for ticket in app.state.ticket_services.tickets._repository.list_tickets():
        if any(request.request_id == UUID(request_id) for request in ticket.feedback_requests):
            return cast(TicketRecord, ticket)
    raise AssertionError(f"Missing feedback request {request_id}")


def fail_audit(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("audit unavailable")

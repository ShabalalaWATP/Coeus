from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.tickets import IntakeDetails
from coeus.main import create_app
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.schemas.store import StoreProductCreateRequest
from coeus.services.analyst_drafts import DraftProductInput, ensure_draft_budget
from coeus.services.audit import AuditLog
from coeus.services.intake import IntakeExtractionService, RequirementCompletenessService
from coeus.services.passwords import PasswordHasher
from coeus.services.ticket_conversations import ConversationService
from coeus.services.tickets import TicketService
from ticket_api_helpers import login


class CountingAssistant:
    def __init__(self) -> None:
        self.calls = 0

    def build_assistant_message(
        self, _intake: IntakeDetails, _safety_flags: tuple[str, ...]
    ) -> str:
        self.calls += 1
        return "Please provide more detail."


def test_chat_count_limit_rejects_before_provider_persistence_and_audit(monkeypatch) -> None:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    actor = SeedUserRepository(settings, PasswordHasher(settings)).get_by_username(
        "user@example.test"
    )
    assert actor is not None
    repository = InMemoryTicketRepository()
    audit = AuditLog()
    assistant = CountingAssistant()
    tickets = TicketService(repository, RequirementCompletenessService(), audit)
    conversations = ConversationService(
        repository, tickets, IntakeExtractionService(), assistant, audit
    )
    ticket = conversations.send_message(actor, "Need a regional port activity brief.")
    calls = assistant.calls
    events = audit.list_events()
    monkeypatch.setattr("coeus.services.ticket_conversations.MAX_CHAT_MESSAGES_PER_TICKET", 2)

    with pytest.raises(AppError) as denied:
        conversations.send_message(actor, "Add the latest reporting period.", ticket.ticket_id)

    assert denied.value.code == "chat_history_limit_reached"
    assert assistant.calls == calls
    assert repository.get(ticket.ticket_id) == ticket
    assert audit.list_events() == events


def test_product_asset_transport_limit_rejects_max_plus_one() -> None:
    asset = {
        "name": "report.pdf",
        "assetType": "document",
        "mimeType": "application/pdf",
        "sizeBytes": 10,
        "sha256": "a" * 64,
    }
    payload = {
        "title": "Example product",
        "summary": "Synthetic summary",
        "description": "Synthetic description",
        "productType": "assessment",
        "sourceType": "synthetic",
        "ownerTeam": "Example team",
        "areaOrRegion": "Example region",
        "classificationLevel": 0,
        "assets": [asset] * 101,
    }

    with pytest.raises(ValidationError):
        StoreProductCreateRequest.model_validate(payload)


def test_draft_budget_rejects_before_version_creation(monkeypatch) -> None:
    monkeypatch.setattr("coeus.services.analyst_drafts.MAX_DRAFT_VERSIONS", 0)
    draft = DraftProductInput("Title", "Summary", "brief", "x" * 20, ())

    with pytest.raises(AppError) as denied:
        ensure_draft_budget((), draft)

    assert denied.value.code == "draft_history_limit_reached"


@pytest.mark.asyncio
async def test_attachment_limit_rejects_atomically(monkeypatch) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client)
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"message": "Need a synthetic regional port activity brief."},
        )
        ticket_id = created.json()["id"]
        stored_id = UUID(ticket_id)
        before = app.state.ticket_services.tickets._repository.get(stored_id)
        monkeypatch.setattr("coeus.services.tickets.MAX_TICKET_ATTACHMENTS", 0)
        response = await client.post(
            f"/api/v1/tickets/{ticket_id}/attachments",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={
                "name": "report.pdf",
                "description": "Synthetic report",
                "sourceType": "document",
            },
        )

    assert response.status_code == 409
    assert "attachment_limit_reached" in response.text
    assert app.state.ticket_services.tickets._repository.get(stored_id) == before


@pytest.mark.asyncio
async def test_ticket_list_uses_stable_cursor_and_compact_summaries() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client)
        for index in range(3):
            created = await client.post(
                "/api/v1/chat/messages",
                headers={"X-CSRF-Token": str(session["csrfToken"])},
                json={"message": f"Need synthetic port report number {index}."},
            )
            assert created.status_code == 201
        first = await client.get("/api/v1/tickets?pageSize=2")
        cursor = first.json()["nextCursor"]
        second = await client.get(f"/api/v1/tickets?pageSize=2&cursor={cursor}")

    assert first.status_code == 200
    assert len(first.json()["tickets"]) == 2
    assert "messages" not in first.json()["tickets"][0]
    assert second.status_code == 200
    assert len(second.json()["tickets"]) == 1
    first_ids = {item["id"] for item in first.json()["tickets"]}
    second_ids = {item["id"] for item in second.json()["tickets"]}
    assert not first_ids & second_ids

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login, submitted_ticket


@pytest.mark.asyncio
async def test_customer_submits_feedback_and_admin_dashboard_tracks_reuse() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    acg_id = _acg_id(app, "ACG-ALPHA-REGIONAL")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        request_id = await _approved_feedback_request(client, app, acg_id)
        user = await login(client, "user@example.test")
        requests = await client.get("/api/v1/feedback/requests")
        submitted = await client.post(
            f"/api/v1/feedback/requests/{request_id}/submit",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={
                "rating": 5,
                "comment": "Useful mock product with clear action points.",
                "followUpRequested": True,
            },
        )
        duplicate = await client.post(
            f"/api/v1/feedback/requests/{request_id}/submit",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"rating": 4, "comment": "Second attempt."},
        )
        admin = await login(client, "admin@example.test")
        dashboard = await client.get("/api/v1/analytics/admin")

    assert requests.status_code == 200
    assert requests.json()["requests"][0]["id"] == request_id
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["submission"]["rating"] == 5
    assert submitted.json()["submission"]["followUpRequested"] is True
    assert duplicate.status_code == 409
    assert dashboard.status_code == 200
    assert dashboard.json()["metrics"]["feedbackSubmitted"] == 1
    assert dashboard.json()["metrics"]["averageRating"] == 5.0
    assert dashboard.json()["productReuse"][0]["feedbackCount"] == 1
    assert "Requester satisfaction" in [item["title"] for item in dashboard.json()["trends"]]
    assert admin["user"]["username"] == "admin@example.test"


@pytest.mark.asyncio
async def test_team_dashboards_are_route_scoped_and_protected() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        await _approved_route_ticket(client, str(user["csrfToken"]), "rfa")
        user = await login(client, "user@example.test")
        await _approved_route_ticket(
            client,
            str(user["csrfToken"]),
            "rfa",
            title="Arctic Review Queue",
            approve=False,
        )
        user = await login(client, "user@example.test")
        await _approved_route_ticket(
            client,
            str(user["csrfToken"]),
            "cm",
            title="Arctic Sensor Collection",
            output_format="collection plan",
        )
        rfa_manager = await login(client, "rfa.manager@example.test")
        rfa_dashboard = await client.get("/api/v1/analytics/rfa")
        forbidden_cm = await client.get("/api/v1/analytics/collection")
        await login(client, "collection.manager@example.test")
        collection_dashboard = await client.get("/api/v1/analytics/collection")
        user = await login(client, "user@example.test")
        forbidden_admin = await client.get("/api/v1/analytics/admin")

    assert rfa_dashboard.status_code == 200
    assert rfa_dashboard.json()["audience"] == "rfa"
    assert rfa_dashboard.json()["metrics"]["rfaRoutes"] == 1
    assert rfa_dashboard.json()["metrics"]["collectionRoutes"] == 0
    assert forbidden_cm.status_code == 403
    assert collection_dashboard.status_code == 200
    assert collection_dashboard.json()["metrics"]["collectionRoutes"] == 1
    assert forbidden_admin.status_code == 403
    assert rfa_manager["user"]["username"] == "rfa.manager@example.test"


async def _approved_feedback_request(client: AsyncClient, app: object, acg_id: str) -> str:
    ticket_id = await _approved_route_ticket(client, "", "rfa")
    analyst_user = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert analyst_user is not None
    manager = await login(client, "rfa.manager@example.test")
    assigned = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/assign",
        headers={"X-CSRF-Token": str(manager["csrfToken"])},
        json={"analystUserId": str(analyst_user.user_id)},
    )
    analyst = await login(client, "analyst@example.test")
    task = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/drafts",
        headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        json=_draft_payload(),
    )
    for package in task.json()["workPackages"]:
        await client.patch(
            f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"status": "complete"},
        )
    submitted = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/submit-qc",
        headers={"X-CSRF-Token": str(analyst["csrfToken"])},
    )
    qc = await login(client, "qc.manager@example.test")
    approved = await client.post(
        f"/api/v1/qc/products/{ticket_id}/approve",
        headers={"X-CSRF-Token": str(qc["csrfToken"])},
        json=_approval_payload(acg_id),
    )
    assert assigned.status_code == 200
    assert submitted.status_code == 200
    assert approved.status_code == 200
    return str(approved.json()["feedbackRequests"][0]["id"])


async def _approved_route_ticket(
    client: AsyncClient,
    csrf_token: str,
    route: str,
    *,
    title: str = "Arctic Fisheries Assessment",
    output_format: str = "assessment report",
    approve: bool = True,
) -> str:
    if not csrf_token:
        user = await login(client, "user@example.test")
        csrf_token = str(user["csrfToken"])
    ticket_id = await submitted_ticket(
        client,
        csrf_token,
        title=title,
        area_or_region="Arctic fisheries",
        output_format=output_format,
    )
    search = await client.post(
        f"/api/v1/rfi-search/{ticket_id}/run",
        headers={"X-CSRF-Token": csrf_token},
    )
    if search.json()["ticketState"] == "RFI_MATCH_OFFERED":
        for offer in search.json()["offers"]:
            await client.post(
                f"/api/v1/rfi-search/{ticket_id}/offers/{offer['productId']}/reject",
                headers={"X-CSRF-Token": csrf_token},
                json={"reason": "Need a new route."},
            )
    manager = await login(
        client,
        "collection.manager@example.test" if route == "cm" else "rfa.manager@example.test",
    )
    routed = await client.post(
        f"/api/v1/routing/{ticket_id}/run",
        headers={"X-CSRF-Token": str(manager["csrfToken"])},
    )
    if not approve:
        assert routed.status_code == 200
        return ticket_id
    approved = await client.post(
        f"/api/v1/routing/{ticket_id}/approve",
        headers={"X-CSRF-Token": str(manager["csrfToken"])},
        json={"route": route},
    )
    assert routed.status_code == 200
    assert approved.status_code == 200
    return ticket_id


def _approval_payload(acg_id: str) -> dict[str, object]:
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


def _draft_payload() -> dict[str, object]:
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


def _acg_id(app: object, code: str) -> str:
    for acg in app.state.access_services.repository.list_acgs():
        if acg.code == code:
            return str(acg.acg_id)
    raise AssertionError(f"Missing seed ACG {code}")

from uuid import uuid4

import pytest
from pydantic import ValidationError

from coeus.schemas.analyst import AnalystAssignmentRequest
from coeus.schemas.routing import RouteClarificationRequest
from coeus.schemas.store import StoreProductCreateRequest
from coeus.schemas.users_admin import UserRolesRequest


def test_store_metadata_list_items_are_bounded() -> None:
    payload = _store_payload()
    payload["tags"] = ["x" * 61]

    with pytest.raises(ValidationError):
        StoreProductCreateRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("releasability", ["NON-MOCK"]),
        ("handlingCaveats", ["UNDEFINED CAVEAT"]),
    ],
)
def test_store_rejects_undefined_release_markers(field: str, value: list[str]) -> None:
    payload = _store_payload()
    payload[field] = value

    with pytest.raises(ValidationError, match="synthetic"):
        StoreProductCreateRequest.model_validate(payload)


def test_store_normalises_supported_synthetic_release_markers() -> None:
    payload = _store_payload()
    payload["releasability"] = [" mock "]
    payload["handlingCaveats"] = [" mock data only "]

    request = StoreProductCreateRequest.model_validate(payload)

    assert request.releasability == ["MOCK"]
    assert request.handling_caveats == ["MOCK DATA ONLY"]


def test_routing_clarification_questions_are_bounded() -> None:
    with pytest.raises(ValidationError):
        RouteClarificationRequest.model_validate(
            {
                "route": "rfa",
                "reason": "Need requester clarification.",
                "questions": ["x" * 301],
            }
        )


def test_analyst_assignment_work_package_items_are_bounded() -> None:
    with pytest.raises(ValidationError):
        AnalystAssignmentRequest.model_validate(
            {
                "analystUserIds": [str(uuid4())],
                "workPackages": ["x" * 181],
            }
        )


def test_admin_role_items_are_bounded() -> None:
    with pytest.raises(ValidationError):
        UserRolesRequest.model_validate({"roles": ["x" * 81]})


def _store_payload() -> dict[str, object]:
    return {
        "title": "Mock Harbour Activity Brief",
        "summary": "Synthetic supporting product.",
        "description": "Synthetic product metadata for schema validation.",
        "productType": "assessment_report",
        "sourceType": "finished_assessment",
        "ownerTeam": "RFA",
        "areaOrRegion": "Baltic ports",
        "classificationLevel": 2,
        "releasability": ["MOCK"],
        "handlingCaveats": ["MOCK DATA ONLY"],
        "tags": ["baltic"],
        "semanticLabels": ["maritime"],
        "acgIds": [str(uuid4())],
        "assets": [
            {
                "name": "supporting-brief.pdf",
                "assetType": "pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 42_000,
                "sha256": "a" * 64,
            }
        ],
    }

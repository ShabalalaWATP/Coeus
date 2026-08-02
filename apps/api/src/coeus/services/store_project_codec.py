from datetime import datetime
from typing import Any
from uuid import UUID

from coeus.domain.store_projects import ProjectActivity, ProjectEntry, StoreProject


def project_payload(project: StoreProject) -> dict[str, Any]:
    return {
        "id": str(project.project_id),
        "ownerUserId": str(project.owner_user_id),
        "name": project.name,
        "purpose": project.purpose,
        "region": project.region,
        "dateFrom": project.date_from,
        "dateTo": project.date_to,
        "archived": project.archived,
        "memberUserIds": [str(item) for item in project.member_user_ids],
        "productIds": [str(item) for item in project.product_ids],
        "entries": [
            {
                "id": str(item.entry_id),
                "authorUserId": str(item.author_user_id),
                "kind": item.kind,
                "body": item.body,
                "createdAt": item.created_at.isoformat(),
            }
            for item in project.entries
        ],
        "activity": [
            {
                "id": str(item.activity_id),
                "actorUserId": str(item.actor_user_id),
                "action": item.action,
                "occurredAt": item.occurred_at.isoformat(),
                "productId": str(item.product_id) if item.product_id else None,
            }
            for item in project.activity
        ],
        "createdAt": project.created_at.isoformat(),
        "updatedAt": project.updated_at.isoformat(),
    }


def project_from_payload(payload: dict[str, Any]) -> StoreProject:
    entries = tuple(
        ProjectEntry(
            UUID(str(item["id"])),
            UUID(str(item["authorUserId"])),
            item["kind"],
            str(item["body"]),
            datetime.fromisoformat(str(item["createdAt"])),
        )
        for item in payload.get("entries", [])
    )
    activity = tuple(
        ProjectActivity(
            UUID(str(item["id"])),
            UUID(str(item["actorUserId"])),
            str(item["action"]),
            datetime.fromisoformat(str(item["occurredAt"])),
            UUID(str(item["productId"])) if item.get("productId") else None,
        )
        for item in payload.get("activity", [])
    )
    return StoreProject(
        project_id=UUID(str(payload["id"])),
        owner_user_id=UUID(str(payload["ownerUserId"])),
        name=str(payload["name"]),
        purpose=str(payload["purpose"]),
        region=payload.get("region"),
        date_from=payload.get("dateFrom"),
        date_to=payload.get("dateTo"),
        archived=bool(payload.get("archived", False)),
        member_user_ids=tuple(UUID(str(item)) for item in payload.get("memberUserIds", [])),
        product_ids=tuple(UUID(str(item)) for item in payload.get("productIds", [])),
        entries=entries,
        activity=activity,
        created_at=datetime.fromisoformat(str(payload["createdAt"])),
        updated_at=datetime.fromisoformat(str(payload["updatedAt"])),
    )

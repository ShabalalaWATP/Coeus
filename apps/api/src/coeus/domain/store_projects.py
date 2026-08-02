from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

EntryKind = Literal["note", "question"]


@dataclass(frozen=True)
class ProjectEntry:
    entry_id: UUID
    author_user_id: UUID
    kind: EntryKind
    body: str
    created_at: datetime


@dataclass(frozen=True)
class ProjectActivity:
    activity_id: UUID
    actor_user_id: UUID
    action: str
    occurred_at: datetime
    product_id: UUID | None = None


@dataclass(frozen=True)
class StoreProject:
    project_id: UUID
    owner_user_id: UUID
    name: str
    purpose: str
    region: str | None
    date_from: str | None
    date_to: str | None
    archived: bool
    member_user_ids: tuple[UUID, ...]
    product_ids: tuple[UUID, ...]
    entries: tuple[ProjectEntry, ...]
    activity: tuple[ProjectActivity, ...]
    created_at: datetime
    updated_at: datetime

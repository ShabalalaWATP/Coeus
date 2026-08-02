from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.store_projects import (
    EntryKind,
    ProjectActivity,
    ProjectEntry,
    StoreProject,
)
from coeus.persistence.state_store import MemoryStateStore, StateStore
from coeus.repositories.access import AccessRepository
from coeus.services.audit import AuditLog
from coeus.services.store_project_codec import project_from_payload, project_payload

PROJECT_NAMESPACE = "store_projects"
MAX_OWNED_PROJECTS = 25
MAX_PROJECT_MEMBERS = 50
MAX_PROJECT_PRODUCTS = 500
MAX_PROJECT_ENTRIES = 200


class StoreProjectService:
    """Persist bounded collaborative context without granting product access."""

    def __init__(
        self,
        state_store: StateStore | None,
        audit_log: AuditLog,
        access_repository: AccessRepository,
    ) -> None:
        self._state_store = state_store or MemoryStateStore()
        self._audit_log = audit_log
        self._access = access_repository
        self._lock: RLock = self._state_store.authority_guard()

    def list_for_user(self, user_id: UUID) -> tuple[StoreProject, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (project for project in self._load() if user_id in project.member_user_ids),
                    key=lambda project: (project.archived, -project.updated_at.timestamp()),
                )
            )

    def get_for_member(self, user_id: UUID, project_id: UUID) -> StoreProject:
        with self._lock:
            return self._member_project(self._load(), user_id, project_id)

    def user_account(self, user_id: UUID) -> UserAccount | None:
        return self._access.get_user(user_id)

    def create(
        self,
        actor: UserAccount,
        *,
        name: str,
        purpose: str,
        region: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> StoreProject:
        clean_name = _required(name, "project_name_required", "Enter a project name.")
        clean_purpose = _required(
            purpose, "project_purpose_required", "Explain what this project is for."
        )
        with self._lock:
            projects = self._load()
            if (
                sum(project.owner_user_id == actor.user_id for project in projects)
                >= MAX_OWNED_PROJECTS
            ):
                raise AppError(409, "project_limit_reached", "The owned project limit is reached.")
            now = datetime.now(UTC)
            project_id = uuid4()
            project = StoreProject(
                project_id=project_id,
                owner_user_id=actor.user_id,
                name=clean_name,
                purpose=clean_purpose,
                region=_optional(region),
                date_from=date_from,
                date_to=date_to,
                archived=False,
                member_user_ids=(actor.user_id,),
                product_ids=(),
                entries=(),
                activity=(_activity(actor.user_id, "project_created", now),),
                created_at=now,
                updated_at=now,
            )
            self._commit(
                projects, (*projects, project), "store_project_created", actor.user_id, project_id
            )
            return project

    def add_member(self, actor: UserAccount, project_id: UUID, username: str) -> StoreProject:
        with self._lock:
            projects = self._load()
            project = self._owned_project(projects, actor.user_id, project_id)
            self._require_active(project)
            member = self._access.get_user_by_username(username.strip())
            if member is None or not member.is_active:
                raise AppError(404, "project_member_not_found", "Active user not found.")
            if member.user_id in project.member_user_ids:
                return project
            if len(project.member_user_ids) >= MAX_PROJECT_MEMBERS:
                raise AppError(
                    409, "project_member_limit_reached", "The project member limit is reached."
                )
            updated = _replace_project(
                project,
                member_user_ids=(*project.member_user_ids, member.user_id),
                actor_user_id=actor.user_id,
                action="project_member_added",
            )
            return self._replace_and_commit(
                projects, updated, "store_project_member_added", actor.user_id
            )

    def remove_member(
        self, actor: UserAccount, project_id: UUID, member_user_id: UUID
    ) -> StoreProject:
        with self._lock:
            projects = self._load()
            project = self._owned_project(projects, actor.user_id, project_id)
            self._require_active(project)
            if member_user_id == project.owner_user_id:
                raise AppError(
                    409, "project_owner_required", "The project owner cannot be removed."
                )
            if member_user_id not in project.member_user_ids:
                raise AppError(404, "project_member_not_found", "Project member not found.")
            updated = _replace_project(
                project,
                member_user_ids=tuple(
                    item for item in project.member_user_ids if item != member_user_id
                ),
                actor_user_id=actor.user_id,
                action="project_member_removed",
            )
            return self._replace_and_commit(
                projects, updated, "store_project_member_removed", actor.user_id
            )

    def set_archived(self, actor: UserAccount, project_id: UUID, archived: bool) -> StoreProject:
        with self._lock:
            projects = self._load()
            project = self._owned_project(projects, actor.user_id, project_id)
            updated = _replace_project(
                project,
                archived=archived,
                actor_user_id=actor.user_id,
                action="project_archived" if archived else "project_restored",
            )
            return self._replace_and_commit(
                projects, updated, "store_project_status_changed", actor.user_id
            )

    def add_product(self, actor: UserAccount, project_id: UUID, product_id: UUID) -> StoreProject:
        with self._lock:
            projects = self._load()
            project = self._member_project(projects, actor.user_id, project_id)
            self._require_active(project)
            if product_id in project.product_ids:
                return project
            if len(project.product_ids) >= MAX_PROJECT_PRODUCTS:
                raise AppError(
                    409, "project_product_limit_reached", "The project product limit is reached."
                )
            updated = _replace_project(
                project,
                product_ids=(*project.product_ids, product_id),
                actor_user_id=actor.user_id,
                action="project_product_added",
                product_id=product_id,
            )
            return self._replace_and_commit(
                projects, updated, "store_project_product_added", actor.user_id
            )

    def remove_product(
        self, actor: UserAccount, project_id: UUID, product_id: UUID
    ) -> StoreProject:
        with self._lock:
            projects = self._load()
            project = self._member_project(projects, actor.user_id, project_id)
            self._require_active(project)
            if product_id not in project.product_ids:
                raise AppError(404, "project_product_not_found", "Project product not found.")
            updated = _replace_project(
                project,
                product_ids=tuple(item for item in project.product_ids if item != product_id),
                actor_user_id=actor.user_id,
                action="project_product_removed",
                product_id=product_id,
            )
            return self._replace_and_commit(
                projects, updated, "store_project_product_removed", actor.user_id
            )

    def add_entry(
        self, actor: UserAccount, project_id: UUID, kind: EntryKind, body: str
    ) -> StoreProject:
        clean_body = _required(body, "project_entry_required", "Enter a note or question.")
        with self._lock:
            projects = self._load()
            project = self._member_project(projects, actor.user_id, project_id)
            self._require_active(project)
            if len(project.entries) >= MAX_PROJECT_ENTRIES:
                raise AppError(
                    409, "project_entry_limit_reached", "The project note limit is reached."
                )
            now = datetime.now(UTC)
            entry = ProjectEntry(uuid4(), actor.user_id, kind, clean_body, now)
            updated = _replace_project(
                project,
                entries=(*project.entries, entry),
                actor_user_id=actor.user_id,
                action=f"project_{kind}_added",
                now=now,
            )
            return self._replace_and_commit(
                projects, updated, f"store_project_{kind}_added", actor.user_id
            )

    @staticmethod
    def _require_active(project: StoreProject) -> None:
        if project.archived:
            raise AppError(409, "project_archived", "Restore the project before changing it.")

    @staticmethod
    def _member_project(
        projects: tuple[StoreProject, ...], user_id: UUID, project_id: UUID
    ) -> StoreProject:
        project = next(
            (
                item
                for item in projects
                if item.project_id == project_id and user_id in item.member_user_ids
            ),
            None,
        )
        if project is None:
            raise AppError(404, "project_not_found", "Project not found.")
        return project

    @classmethod
    def _owned_project(
        cls, projects: tuple[StoreProject, ...], user_id: UUID, project_id: UUID
    ) -> StoreProject:
        project = cls._member_project(projects, user_id, project_id)
        if project.owner_user_id != user_id:
            raise AppError(403, "project_owner_required", "Only the project owner can do that.")
        return project

    def _replace_and_commit(
        self,
        projects: tuple[StoreProject, ...],
        updated: StoreProject,
        event_type: str,
        actor_user_id: UUID,
    ) -> StoreProject:
        next_projects = tuple(
            updated if item.project_id == updated.project_id else item for item in projects
        )
        self._commit(projects, next_projects, event_type, actor_user_id, updated.project_id)
        return updated

    def _load(self) -> tuple[StoreProject, ...]:
        payload = self._state_store.load(PROJECT_NAMESPACE) or {}
        return tuple(project_from_payload(item) for item in payload.get("projects", []))

    def _save(self, projects: tuple[StoreProject, ...]) -> None:
        self._state_store.save(
            PROJECT_NAMESPACE, {"projects": [project_payload(item) for item in projects]}
        )

    def _commit(
        self,
        previous: tuple[StoreProject, ...],
        updated: tuple[StoreProject, ...],
        event_type: str,
        actor_user_id: UUID,
        project_id: UUID,
    ) -> None:
        self._save(updated)
        try:
            self._audit_log.record(event_type, str(actor_user_id), {"project_id": str(project_id)})
        except Exception:
            self._save(previous)
            raise


def _replace_project(project: StoreProject, **changes: Any) -> StoreProject:
    now = changes.pop("now", datetime.now(UTC))
    actor_user_id = changes.pop("actor_user_id")
    action = changes.pop("action")
    product_id = changes.pop("product_id", None)
    values = {field: getattr(project, field) for field in project.__dataclass_fields__}
    values.update(changes)
    values["updated_at"] = now
    values["activity"] = (*project.activity, _activity(actor_user_id, action, now, product_id))
    return StoreProject(**values)


def _activity(
    actor_user_id: UUID, action: str, occurred_at: datetime, product_id: UUID | None = None
) -> ProjectActivity:
    return ProjectActivity(uuid4(), actor_user_id, action, occurred_at, product_id)


def _required(value: str, code: str, message: str) -> str:
    clean = value.strip()
    if not clean:
        raise AppError(422, code, message)
    return clean


def _optional(value: str | None) -> str | None:
    clean = value.strip() if value else ""
    return clean or None

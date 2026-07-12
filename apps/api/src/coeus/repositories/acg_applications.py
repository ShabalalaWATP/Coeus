from dataclasses import dataclass
from threading import RLock
from uuid import UUID

from coeus.domain.access import AcgAccessApplication, AcgApplicationStatus
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore


@dataclass(frozen=True)
class AcgWorkflowSnapshot:
    administrators: dict[UUID, frozenset[UUID]]
    applications: dict[UUID, AcgAccessApplication]
    initialised_acg_ids: frozenset[UUID]


class AcgApplicationRepository:
    """Single-writer state for delegated ACG governance and applications."""

    def __init__(self, state_store: StateStore | None = None) -> None:
        self._state_store = state_store
        self._lock = RLock()
        self._administrators: dict[UUID, frozenset[UUID]] = {}
        self._applications: dict[UUID, AcgAccessApplication] = {}
        self._initialised_acg_ids: set[UUID] = set()
        self._restore()

    def snapshot(self) -> AcgWorkflowSnapshot:
        with self._lock:
            return AcgWorkflowSnapshot(
                administrators=dict(self._administrators),
                applications=dict(self._applications),
                initialised_acg_ids=frozenset(self._initialised_acg_ids),
            )

    def restore(self, snapshot: AcgWorkflowSnapshot) -> None:
        with self._lock:
            previous = self.snapshot()
            self._administrators = dict(snapshot.administrators)
            self._applications = dict(snapshot.applications)
            self._initialised_acg_ids = set(snapshot.initialised_acg_ids)
            try:
                self._persist()
            except Exception:
                self._administrators = previous.administrators
                self._applications = previous.applications
                self._initialised_acg_ids = set(previous.initialised_acg_ids)
                raise

    def admin_user_ids(self, acg_id: UUID) -> frozenset[UUID]:
        with self._lock:
            return self._administrators.get(acg_id, frozenset())

    def is_admin(self, acg_id: UUID, user_id: UUID) -> bool:
        return user_id in self.admin_user_ids(acg_id)

    def is_initialised(self, acg_id: UUID) -> bool:
        with self._lock:
            return acg_id in self._initialised_acg_ids

    def replace_admins(self, acg_id: UUID, user_ids: frozenset[UUID]) -> None:
        with self._lock:
            previous = self.snapshot()
            self._administrators[acg_id] = user_ids
            self._initialised_acg_ids.add(acg_id)
            self._persist_or_restore(previous)

    def get_for_user(self, acg_id: UUID, user_id: UUID) -> AcgAccessApplication | None:
        with self._lock:
            matching = (
                application
                for application in self._applications.values()
                if application.acg_id == acg_id and application.applicant_user_id == user_id
            )
            return max(
                matching,
                key=lambda item: (item.submitted_at, str(item.application_id)),
                default=None,
            )

    def get_by_id(self, application_id: UUID) -> AcgAccessApplication | None:
        with self._lock:
            return self._applications.get(application_id)

    def save(self, application: AcgAccessApplication) -> None:
        with self._lock:
            previous = self.snapshot()
            self._applications[application.application_id] = application
            self._persist_or_restore(previous)

    def list_pending(self, acg_ids: frozenset[UUID]) -> tuple[AcgAccessApplication, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        application
                        for application in self._applications.values()
                        if application.acg_id in acg_ids
                        and application.status == AcgApplicationStatus.PENDING
                    ),
                    key=lambda item: (item.submitted_at, str(item.application_id)),
                )
            )

    def _persist_or_restore(self, previous: AcgWorkflowSnapshot) -> None:
        try:
            self._persist()
        except Exception:
            self._administrators = previous.administrators
            self._applications = previous.applications
            self._initialised_acg_ids = set(previous.initialised_acg_ids)
            raise

    def _restore(self) -> None:
        if self._state_store is None:
            return
        payload = self._state_store.load("acg_workflows")
        if payload is None:
            self._persist()
            return
        administrators = payload.get("administrators", {})
        self._administrators = {
            UUID(acg_id): frozenset(UUID(user_id) for user_id in user_ids)
            for acg_id, user_ids in administrators.items()
        }
        self._initialised_acg_ids = {
            UUID(acg_id) for acg_id in payload.get("initialised_acg_ids", administrators.keys())
        }
        applications = tuple(decode_value(item) for item in payload.get("applications", []))
        self._applications = {item.application_id: item for item in applications}

    def _persist(self) -> None:
        if self._state_store is None:
            return
        self._state_store.save(
            "acg_workflows",
            {
                "administrators": {
                    str(acg_id): [str(user_id) for user_id in sorted(user_ids, key=str)]
                    for acg_id, user_ids in sorted(
                        self._administrators.items(), key=lambda item: str(item[0])
                    )
                },
                "applications": [
                    encode_value(item)
                    for item in sorted(
                        self._applications.values(), key=lambda item: str(item.application_id)
                    )
                ],
                "initialised_acg_ids": [
                    str(acg_id) for acg_id in sorted(self._initialised_acg_ids, key=str)
                ],
            },
        )

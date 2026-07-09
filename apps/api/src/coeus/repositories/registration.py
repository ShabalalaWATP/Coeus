from uuid import UUID

from coeus.domain.registration import RegistrationRequest, RegistrationStatus
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore


class RegistrationRepository:
    def __init__(self, state_store: StateStore | None = None) -> None:
        self._state_store = state_store
        self._registrations: dict[UUID, RegistrationRequest] = {}
        self._restore_or_persist()

    def save(self, registration: RegistrationRequest) -> None:
        self._registrations[registration.registration_id] = registration
        self._persist()

    def delete(self, registration_id: UUID) -> None:
        self._registrations.pop(registration_id, None)
        self._persist()

    def get(self, registration_id: UUID) -> RegistrationRequest | None:
        return self._registrations.get(registration_id)

    def list_pending(self) -> tuple[RegistrationRequest, ...]:
        return tuple(
            sorted(
                (
                    registration
                    for registration in self._registrations.values()
                    if registration.status == RegistrationStatus.PENDING
                ),
                key=lambda registration: registration.created_at,
            )
        )

    def pending_count(self) -> int:
        return len(self.list_pending())

    def has_pending_username(self, username: str) -> bool:
        casefolded = username.casefold()
        return any(
            registration.username.casefold() == casefolded
            for registration in self._registrations.values()
            if registration.status == RegistrationStatus.PENDING
        )

    def _restore_or_persist(self) -> None:
        if self._state_store is None:
            return
        payload = self._state_store.load("registrations")
        if payload is None:
            self._persist()
            return
        registrations = tuple(decode_value(item) for item in payload.get("registrations", []))
        self._registrations = {
            registration.registration_id: registration for registration in registrations
        }

    def _persist(self) -> None:
        if self._state_store is None:
            return
        registrations = sorted(
            self._registrations.values(), key=lambda registration: registration.created_at
        )
        self._state_store.save(
            "registrations",
            {"registrations": [encode_value(registration) for registration in registrations]},
        )

from uuid import UUID

from coeus.domain.registration import RegistrationRequest, RegistrationStatus


class RegistrationRepository:
    def __init__(self) -> None:
        self._registrations: dict[UUID, RegistrationRequest] = {}

    def save(self, registration: RegistrationRequest) -> None:
        self._registrations[registration.registration_id] = registration

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

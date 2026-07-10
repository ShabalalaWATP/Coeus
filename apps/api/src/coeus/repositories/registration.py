from dataclasses import dataclass
from threading import RLock
from uuid import UUID, uuid4

from coeus.domain.registration import RegistrationRequest, RegistrationStatus
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore


class RegistrationCapacityFull(RuntimeError):
    """Raised when pending registrations and active reservations reach capacity."""


@dataclass(frozen=True)
class RegistrationReservation:
    reservation_id: UUID
    username: str


class RegistrationRepository:
    def __init__(self, state_store: StateStore | None = None) -> None:
        self._state_store = state_store
        self._lock = RLock()
        self._registrations: dict[UUID, RegistrationRequest] = {}
        self._reservations: dict[UUID, str] = {}
        self._restore_or_persist()

    def save(self, registration: RegistrationRequest) -> None:
        with self._lock:
            registrations = dict(self._registrations)
            self._registrations[registration.registration_id] = registration
            try:
                self._persist()
            except Exception:
                self._registrations = registrations
                raise

    def reserve_pending_slot(
        self, username: str, max_pending: int
    ) -> RegistrationReservation | None:
        casefolded = username.casefold()
        with self._lock:
            if self._has_pending_username(casefolded):
                return None
            if self._pending_count() + len(self._reservations) >= max_pending:
                raise RegistrationCapacityFull("Registration capacity is full.")
            reservation = RegistrationReservation(uuid4(), casefolded)
            self._reservations[reservation.reservation_id] = casefolded
            return reservation

    def commit_reserved(
        self,
        reservation: RegistrationReservation,
        registration: RegistrationRequest,
    ) -> None:
        with self._lock:
            reserved_username = self._reservations.get(reservation.reservation_id)
            if reserved_username != registration.username.casefold():
                raise RuntimeError("Registration reservation is missing or does not match.")
            registrations = dict(self._registrations)
            self._registrations[registration.registration_id] = registration
            self._reservations.pop(reservation.reservation_id)
            try:
                self._persist()
            except Exception:
                self._registrations = registrations
                self._reservations[reservation.reservation_id] = reserved_username
                raise

    def release_reservation(self, reservation: RegistrationReservation) -> None:
        with self._lock:
            self._reservations.pop(reservation.reservation_id, None)

    def delete(self, registration_id: UUID) -> None:
        with self._lock:
            registrations = dict(self._registrations)
            self._registrations.pop(registration_id, None)
            try:
                self._persist()
            except Exception:
                self._registrations = registrations
                raise

    def get(self, registration_id: UUID) -> RegistrationRequest | None:
        with self._lock:
            return self._registrations.get(registration_id)

    def list_pending(self) -> tuple[RegistrationRequest, ...]:
        with self._lock:
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
        with self._lock:
            return self._pending_count()

    def has_pending_username(self, username: str) -> bool:
        casefolded = username.casefold()
        with self._lock:
            return self._has_pending_username(casefolded)

    @property
    def reservation_count(self) -> int:
        with self._lock:
            return len(self._reservations)

    def _has_pending_username(self, casefolded: str) -> bool:
        return (
            any(
                registration.username.casefold() == casefolded
                for registration in self._registrations.values()
                if registration.status == RegistrationStatus.PENDING
            )
            or casefolded in self._reservations.values()
        )

    def _pending_count(self) -> int:
        return sum(
            registration.status == RegistrationStatus.PENDING
            for registration in self._registrations.values()
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

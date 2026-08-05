"""Application boundary for conserved personal capacity."""

from typing import Protocol

from coeus.domain.work_packages import CapacityReservation, ReserveCapacityCommand


class CapacityReservationStore(Protocol):
    def reserve(self, command: ReserveCapacityCommand) -> CapacityReservation: ...

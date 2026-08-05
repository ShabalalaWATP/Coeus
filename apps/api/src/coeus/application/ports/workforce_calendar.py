"""Application ports for canonical workforce calendar persistence."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from coeus.domain.calendar_commitments import CalendarCommitment, CalendarCommitmentResponse
from coeus.domain.organisation import ManagementAction
from coeus.domain.workforce_calendar import (
    CalendarEvent,
    CalendarMutationCommand,
    CalendarMutationRequest,
    CalendarMutationResult,
    CalendarMutationSnapshot,
    ScopedCalendarEvent,
)


class WorkforceCalendarStore(Protocol):
    def get_event(self, event_id: UUID) -> CalendarEvent | None: ...

    def list_owner_events(
        self, owner_user_id: UUID, window_start: datetime, window_end: datetime
    ) -> tuple[CalendarEvent, ...]: ...

    def list_unit_events(
        self,
        actor_user_id: UUID,
        authorising_grant_id: UUID,
        action: ManagementAction,
        root_unit_id: UUID,
        unit_ids: tuple[UUID, ...],
        window_start: datetime,
        window_end: datetime,
    ) -> tuple[ScopedCalendarEvent, ...]: ...

    def inspect(self, request: CalendarMutationRequest) -> CalendarMutationSnapshot: ...

    def replay(self, command: CalendarMutationCommand) -> CalendarMutationResult | None: ...

    def apply(self, command: CalendarMutationCommand) -> CalendarMutationResult: ...

    def list_commitments(self, subject_user_id: UUID) -> tuple[CalendarCommitment, ...]: ...

    def respond_commitment(self, response: CalendarCommitmentResponse) -> CalendarCommitment: ...

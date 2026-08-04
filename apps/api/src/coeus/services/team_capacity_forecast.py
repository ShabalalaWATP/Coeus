"""Identity-aware advisory team capacity forecast service."""

from datetime import datetime, timedelta
from uuid import UUID

from coeus.application.ports.team_capacity_forecast import TeamCapacityForecastStore
from coeus.domain.team_capacity_forecast import TeamCapacityForecast


class TeamCapacityForecastService:
    def __init__(self, store: TeamCapacityForecastStore) -> None:
        self._store = store

    def forecast(
        self,
        actor_user_id: UUID,
        unit_id: UUID,
        authorising_grant_id: UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> TeamCapacityForecast:
        if window_start.tzinfo is None or window_end.tzinfo is None:
            raise ValueError("forecast bounds must be timezone-aware")
        if window_start >= window_end or window_end - window_start > timedelta(days=31):
            raise ValueError("forecast window must be positive and no longer than 31 days")
        return self._store.forecast(
            actor_user_id,
            unit_id,
            authorising_grant_id,
            window_start,
            window_end,
        )

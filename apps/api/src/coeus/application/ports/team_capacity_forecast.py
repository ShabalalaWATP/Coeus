"""Application boundary for advisory team capacity forecasts."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from coeus.domain.team_capacity_forecast import TeamCapacityForecast


class TeamCapacityForecastStore(Protocol):
    def forecast(
        self,
        actor_user_id: UUID,
        unit_id: UUID,
        authorising_grant_id: UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> TeamCapacityForecast: ...

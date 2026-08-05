"""Bounded capacity and availability scenarios for the exercise workforce."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.repositories.synthetic_organisation_manifest import BASELINE
from coeus.repositories.synthetic_task_manifest import synthetic_task_specs


@dataclass(frozen=True)
class SyntheticCapacityReservationSpec:
    key: str
    task_key: str
    minutes: int
    offset_days: int

    @property
    def reservation_id(self) -> UUID:
        return uuid5(NAMESPACE_URL, f"coeus:synthetic-capacity:v1:{self.key}")

    @property
    def starts_at(self) -> datetime:
        return BASELINE + timedelta(days=self.offset_days, hours=8)

    @property
    def ends_at(self) -> datetime:
        return BASELINE + timedelta(days=self.offset_days, hours=16)


@dataclass(frozen=True)
class SyntheticWorkloadScenario:
    state: str
    username: str
    reserved_minutes: int
    active_work_minutes: int
    daily_capacity_minutes: int


def synthetic_capacity_reservations() -> tuple[SyntheticCapacityReservationSpec, ...]:
    return (
        SyntheticCapacityReservationSpec("loaded", "reg-2", 180, 8),
        SyntheticCapacityReservationSpec("overloaded", "land-1", 480, 8),
    )


def synthetic_workload_scenarios() -> tuple[SyntheticWorkloadScenario, ...]:
    tasks = {item.key: item for item in synthetic_task_specs()}
    assigned = {
        item.assignee_username
        for item in tasks.values()
        if item.assignee_username and not item.ticket_state.value.startswith("CLOSED_")
    }
    all_eligible = (
        "analyst@example.test",
        *(f"analyst.{index}@example.test" for index in range(2, 24)),
    )
    idle = next(username for username in all_eligible if username not in assigned)
    return (
        SyntheticWorkloadScenario("idle", idle, 0, 0, 480),
        SyntheticWorkloadScenario("loaded", tasks["reg-2"].assignee_username or "", 180, 240, 480),
        SyntheticWorkloadScenario(
            "overloaded", tasks["land-1"].assignee_username or "", 480, 300, 480
        ),
        SyntheticWorkloadScenario("unavailable", "analyst.24@example.test", 0, 0, 0),
    )

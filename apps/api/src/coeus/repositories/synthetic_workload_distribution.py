"""Stable capacity-aware assignment for the exercise task manifest."""

from collections import defaultdict
from dataclasses import replace
from typing import TYPE_CHECKING

from coeus.domain.organisation import MembershipState
from coeus.repositories.synthetic_organisation_manifest import (
    BASELINE,
    synthetic_posting_specs,
    synthetic_working_patterns,
)

_PRIORITY_MINUTES = {"Urgent": 600, "High": 480, "Routine": 360}

if TYPE_CHECKING:
    from coeus.repositories.synthetic_task_manifest import SyntheticTaskSpec


def distribute_synthetic_tasks(
    tasks: tuple["SyntheticTaskSpec", ...],
) -> tuple["SyntheticTaskSpec", ...]:
    """Assign marked tasks by home team, projected load and manifest order.

    The allocator never infers authority from a name. It admits only effective,
    active, assignment-eligible postings and uses the working pattern as the
    capacity denominator. Ties retain posting order so fixture output is stable.
    """
    from coeus.repositories.synthetic_task_manifest import SyntheticTaskSpec

    candidates: dict[str, list[str]] = defaultdict(list)
    for posting in synthetic_posting_specs():
        if (
            posting.state is MembershipState.ACTIVE
            and posting.assignment_eligible
            and posting.valid_from <= BASELINE
            and (posting.valid_until is None or posting.valid_until > BASELINE)
        ):
            candidates[posting.unit_key].append(posting.username)
    weekly = {item.username: item.weekday_minutes * 5 for item in synthetic_working_patterns()}
    load: dict[str, int] = defaultdict(int)
    assigned: list[SyntheticTaskSpec] = []
    for task in tasks:
        if task.assignee_username != "__capacity_allocate__":
            assigned.append(task)
            continue
        pool = candidates[task.unit_key]
        if not pool:
            raise ValueError(f"No eligible synthetic analyst for {task.unit_key}.")
        owner = min(
            pool,
            key=lambda username: (load[username] / weekly[username], pool.index(username)),
        )
        assigned.append(replace(task, assignee_username=owner))
        if not task.ticket_state.value.startswith("CLOSED_"):
            load[owner] += _PRIORITY_MINUTES[task.priority]
    return tuple(assigned)

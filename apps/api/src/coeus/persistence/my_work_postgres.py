"""Actor-scoped canonical personal work projection."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine, RowMapping

from coeus.application.ports.my_work import MyWorkStore
from coeus.domain.enums import TicketState
from coeus.domain.my_work import (
    MyWorkCard,
    MyWorkColumn,
    MyWorkCursor,
    MyWorkIntegrityError,
    MyWorkPage,
    decode_cursor,
    encode_cursor,
)
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.tickets import TicketRecord
from coeus.persistence.codec import decode_value

_MAX_CANDIDATES = 501


class PostgresMyWorkStore(MyWorkStore):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list_my_work(
        self,
        actor_user_id: UUID,
        *,
        include_completed: bool,
        column: MyWorkColumn | None,
        cursor: str | None,
        limit: int,
    ) -> MyWorkPage:
        decoded_cursor = decode_cursor(cursor)
        with (
            self._engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            as_of = connection.execute(text("SELECT transaction_timestamp()")).scalar_one()
            rows = tuple(
                connection.execute(
                    text(_QUERY),
                    {
                        "actor_id": actor_user_id,
                        "as_of": as_of,
                        "include_completed": include_completed,
                        "column": column.value if column else None,
                        "cursor_sort_at": decoded_cursor.sort_at if decoded_cursor else None,
                        "cursor_ticket_id": decoded_cursor.ticket_id if decoded_cursor else None,
                        "cursor_leg": (
                            decoded_cursor.workflow_leg.value if decoded_cursor else None
                        ),
                        "cursor_order": decoded_cursor.sort_order if decoded_cursor else None,
                        "cursor_package_id": decoded_cursor.package_id if decoded_cursor else None,
                        "limit": min(limit + 1, _MAX_CANDIDATES),
                    },
                ).mappings()
            )
            cards = tuple(_card(row) for row in rows[:limit])
            next_cursor = _next_cursor(rows[limit - 1]) if len(rows) > limit else None
            return MyWorkPage(cards, as_of, next_cursor)


def _card(row: RowMapping) -> MyWorkCard:
    ticket_id = UUID(str(row["ticket_id"]))
    package_id = UUID(str(row["package_id"]))
    value = decode_value(dict(row["payload"]))
    if not isinstance(value, TicketRecord) or value.ticket_id != ticket_id:
        raise MyWorkIntegrityError("ticket aggregate identity mismatch")
    try:
        workflow_leg = WorkflowLeg(str(row["workflow_leg"]))
        column = MyWorkColumn(str(row["my_column"]))
        expected_column = _column(value.state, str(row["package_state"]))
        accountable_id = _optional_uuid(row["accountable_user_id"])
        actor_id = UUID(str(row["participant_user_id"]))
        role = str(row["participant_role"])
        if column is not expected_column:
            raise ValueError
        if role == "accountable" and accountable_id != actor_id:
            raise ValueError
        if role == "contributor" and accountable_id == actor_id:
            raise ValueError
        return MyWorkCard(
            ticket_id=ticket_id,
            workflow_leg=workflow_leg,
            package_id=package_id,
            reference=value.reference,
            ticket_title=value.intake.title or "Untitled request",
            package_title=str(row["package_title"]),
            column=column,
            priority=int(row["priority"]) if row["priority"] is not None else None,
            target_date=row["target_date"],
            due_at=row["due_at"],
            blocked_code=str(row["blocked_code"]) if row["blocked_code"] else None,
            review_at=row["review_at"],
            ticket_version=int(row["ticket_version"]),
            ownership_version=int(row["ownership_version"]),
            package_version=int(row["package_version"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MyWorkIntegrityError("personal work projection is malformed") from exc


def _column(ticket_state: TicketState, package_state: str) -> MyWorkColumn:
    if ticket_state in {TicketState.MANAGER_APPROVAL, TicketState.QC_REVIEW}:
        return MyWorkColumn.REVIEW
    if ticket_state is TicketState.REWORK_REQUIRED:
        return MyWorkColumn.REWORK
    if ticket_state is TicketState.JIOC_INTERVENTION_HOLD:
        return MyWorkColumn.ON_HOLD
    if package_state == "blocked":
        return MyWorkColumn.BLOCKED
    if package_state in {"complete", "cancelled"} or _closed(ticket_state):
        return MyWorkColumn.COMPLETED
    if package_state in {"pending", "ready"}:
        return MyWorkColumn.READY
    if package_state == "in_progress":
        return MyWorkColumn.IN_PROGRESS
    raise MyWorkIntegrityError("personal work state is unsupported")


def _closed(state: TicketState) -> bool:
    return state.value.startswith("CLOSED_") or state is TicketState.CANCELLED


def _optional_uuid(value: object) -> UUID | None:
    return UUID(str(value)) if value is not None else None


def _next_cursor(row: RowMapping) -> str:
    sort_at = row["sort_at"]
    if not isinstance(sort_at, datetime):
        raise MyWorkIntegrityError("personal work ordering is malformed")
    return encode_cursor(
        MyWorkCursor(
            sort_at.astimezone(UTC),
            UUID(str(row["ticket_id"])),
            WorkflowLeg(str(row["workflow_leg"])),
            int(row["sort_order"]),
            UUID(str(row["package_id"])),
        )
    )


_QUERY = """
WITH personal_work AS (
  SELECT package.package_id,package.ticket_id,package.workflow_leg,package.title package_title,
         package.state package_state,package.accountable_user_id,package.priority,
         package.due_at,package.blocked_code,package.review_at,package.sort_order,
         package.version package_version,participant.user_id participant_user_id,
         participant.role participant_role,ownership.target_date,
         ownership.version ownership_version,aggregate.version ticket_version,
         aggregate.updated_at ticket_updated_at,aggregate.payload,
         CASE
           WHEN aggregate.state IN ('MANAGER_APPROVAL','QC_REVIEW') THEN 'review'
           WHEN aggregate.state='REWORK_REQUIRED' THEN 'rework'
           WHEN aggregate.state='JIOC_INTERVENTION_HOLD' THEN 'on_hold'
           WHEN package.state='blocked' THEN 'blocked'
           WHEN package.state IN ('complete','cancelled')
                OR aggregate.state LIKE 'CLOSED_%'
                OR aggregate.state='CANCELLED' THEN 'completed'
           WHEN package.state IN ('pending','ready') THEN 'ready'
           WHEN package.state='in_progress' THEN 'in_progress'
           ELSE 'unsupported'
         END AS my_column,
         COALESCE(package.review_at,package.due_at,'9999-12-31 23:59:59+00'::timestamptz)
           AS sort_at
  FROM work_package_participants participant
  JOIN canonical_work_packages package ON package.package_id=participant.package_id
  JOIN team_task_ownership ownership
    ON ownership.ticket_id=package.ticket_id
   AND ownership.workflow_leg=package.workflow_leg
   AND ownership.owning_unit_id=package.owning_unit_id
  JOIN coeus_ticket_aggregates aggregate ON aggregate.ticket_id=package.ticket_id
  WHERE participant.user_id=:actor_id AND participant.active
    AND ownership.state NOT IN ('cancelled','ownership_unresolved')
)
SELECT * FROM personal_work
WHERE my_column<>'unsupported'
  AND (:include_completed OR my_column<>'completed')
  AND (my_column<>'completed' OR ticket_updated_at>=:as_of - interval '30 days')
  AND (CAST(:column AS text) IS NULL OR my_column=CAST(:column AS text))
  AND (
    CAST(:cursor_sort_at AS timestamptz) IS NULL OR
    (sort_at,ticket_id,workflow_leg,sort_order,package_id) >
    (CAST(:cursor_sort_at AS timestamptz),CAST(:cursor_ticket_id AS uuid),
     CAST(:cursor_leg AS text),CAST(:cursor_order AS integer),
     CAST(:cursor_package_id AS uuid))
  )
ORDER BY sort_at,ticket_id,workflow_leg,sort_order,package_id
LIMIT :limit
"""

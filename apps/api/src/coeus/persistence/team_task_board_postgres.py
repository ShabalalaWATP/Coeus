"""Transactionally authorised canonical team and management board projection."""

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine, RowMapping

from coeus.application.ports.team_task_board import TeamTaskBoardStore
from coeus.domain.enums import TicketState
from coeus.domain.team_task_board import (
    TeamBoardAggregate,
    TeamBoardColumn,
    TeamBoardCursor,
    TeamBoardQuery,
    TeamTaskBoard,
    TeamTaskBoardIntegrityError,
    TeamTaskCard,
    TeamTaskPackage,
    decode_board_cursor,
    encode_board_cursor,
)
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.tickets import TicketRecord
from coeus.persistence.codec import decode_value
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.team_task_board_authority import resolve_board_authority
from coeus.persistence.team_task_board_sql import AGGREGATES, DETAIL

_MAX_CANDIDATES = 501


class PostgresTeamTaskBoardStore(TeamTaskBoardStore):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_board(
        self,
        actor_user_id: UUID,
        unit_id: UUID,
        query: TeamBoardQuery | None = None,
        *,
        include_completed: bool = False,
        limit: int = 50,
    ) -> TeamTaskBoard:
        query = query or TeamBoardQuery(include_completed=include_completed, limit=limit)
        cursor = decode_board_cursor(query.cursor)
        with (
            self._engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            effective_at = transaction_time(connection)
            completed_after = _completed_after(query.completed_after, effective_at)
            authority = resolve_board_authority(
                connection, actor_user_id, unit_id, query, effective_at
            )
            params = _params(query, cursor, completed_after)
            rows = tuple(
                connection.execute(
                    text(DETAIL),
                    {**params, "unit_ids": list(authority.detail_unit_ids)},
                ).mappings()
                if authority.detail_unit_ids
                else ()
            )
            matching = tuple((row, _card(row)) for row in rows if _matches(row, query))
            cards = tuple(card for _, card in matching[: query.limit])
            truncated = len(matching) > query.limit or len(rows) == _MAX_CANDIDATES
            cursor_row = _cursor_row(rows, matching, query.limit, truncated)
            aggregate_rows = tuple(
                connection.execute(
                    text(AGGREGATES),
                    {**params, "unit_ids": list(authority.aggregate_unit_ids)},
                ).mappings()
                if authority.aggregate_unit_ids
                else ()
            )
            aggregates = tuple(_aggregate(row) for row in aggregate_rows)
            return TeamTaskBoard(
                unit_id,
                cards,
                effective_at,
                truncated,
                _row_cursor(cursor_row) if cursor_row else None,
                aggregates,
                query.scope,
            )


def _card(row: RowMapping) -> TeamTaskCard:
    value = decode_value(dict(row["payload"]))
    if not isinstance(value, TicketRecord) or value.ticket_id != UUID(str(row["ticket_id"])):
        raise TeamTaskBoardIntegrityError("ticket aggregate identity mismatch")
    packages = tuple(_package(item) for item in row["packages"])
    column = _column(value.state, packages)
    if column.value != str(row["board_column"]):
        raise TeamTaskBoardIntegrityError("board state projection mismatch")
    return TeamTaskCard(
        value.ticket_id,
        WorkflowLeg(str(row["workflow_leg"])),
        value.reference,
        value.intake.title or "Untitled request",
        column,
        value.intake.priority or "Not set",
        row["target_date"],
        row["ticket_updated_at"],
        int(row["ticket_version"]),
        int(row["ownership_version"]),
        packages,
        UUID(str(row["owning_unit_id"])),
        str(row["unit_name"]),
    )


def _package(value: object) -> TeamTaskPackage:
    if not isinstance(value, dict):
        raise TeamTaskBoardIntegrityError("work package projection is malformed")
    try:
        return TeamTaskPackage(
            UUID(str(value["package_id"])),
            str(value["title"]),
            str(value["state"]),
            UUID(str(value["accountable_user_id"]))
            if value["accountable_user_id"] is not None
            else None,
            int(value["estimated_minutes"]) if value["estimated_minutes"] is not None else None,
            int(value["remaining_minutes"]) if value["remaining_minutes"] is not None else None,
            _optional_datetime(value["due_at"]),
            int(value["priority"]) if value["priority"] is not None else None,
            int(value["version"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TeamTaskBoardIntegrityError("work package projection is malformed") from exc


def _optional_datetime(value: object) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError("work package date is malformed")


def _column(state: TicketState, packages: tuple[TeamTaskPackage, ...] = ()) -> TeamBoardColumn:
    mapping = {
        TicketState.ANALYST_ASSIGNMENT: TeamBoardColumn.AWAITING_ASSIGNMENT,
        TicketState.MANAGER_APPROVAL: TeamBoardColumn.MANAGER_REVIEW,
        TicketState.QC_REVIEW: TeamBoardColumn.QC_REVIEW,
        TicketState.REWORK_REQUIRED: TeamBoardColumn.REWORK,
        TicketState.JIOC_INTERVENTION_HOLD: TeamBoardColumn.ON_HOLD,
    }
    if state is TicketState.ANALYST_IN_PROGRESS:
        incomplete = tuple(item for item in packages if item.state not in {"complete", "cancelled"})
        if incomplete and all(item.state == "blocked" for item in incomplete):
            return TeamBoardColumn.BLOCKED
        if packages and not any(
            item.state in {"in_progress", "blocked", "complete"} for item in packages
        ):
            return TeamBoardColumn.READY
        return TeamBoardColumn.IN_PROGRESS
    if state in mapping:
        return mapping[state]
    if state.value.startswith("CLOSED_") or state is TicketState.CANCELLED:
        return TeamBoardColumn.COMPLETED_RECENTLY
    raise TeamTaskBoardIntegrityError("ticket state is not supported by the delivery board")


def _completed_after(value: date | None, effective_at: datetime) -> date:
    earliest = effective_at.date() - timedelta(days=90)
    resolved = value or effective_at.date() - timedelta(days=30)
    if resolved < earliest or resolved > effective_at.date():
        raise ValueError("completed_after must be within the previous 90 days")
    return resolved


def _params(
    query: TeamBoardQuery,
    cursor: TeamBoardCursor | None,
    completed_after: date,
) -> dict[str, object]:
    return {
        "include_completed": query.include_completed,
        "completed_after": completed_after,
        "columns": [column.value for column in query.columns],
        "due_from": query.due_from,
        "due_to": query.due_to,
        "cursor_unit": cursor.unit_id if cursor else None,
        "cursor_date": cursor.target_date if cursor else None,
        "cursor_ticket": cursor.ticket_id if cursor else None,
        "cursor_leg": cursor.workflow_leg.value if cursor else None,
        "candidate_limit": _MAX_CANDIDATES,
    }


def _matches(row: RowMapping, query: TeamBoardQuery) -> bool:
    if query.priority is None:
        return True
    value = decode_value(dict(row["payload"]))
    return isinstance(value, TicketRecord) and (value.intake.priority or "Not set").casefold() == (
        query.priority.casefold()
    )


def _cursor_row(
    rows: tuple[RowMapping, ...],
    matching: tuple[tuple[RowMapping, TeamTaskCard], ...],
    limit: int,
    truncated: bool,
) -> RowMapping | None:
    if not truncated:
        return None
    if len(matching) > limit:
        return matching[limit - 1][0]
    return rows[-1] if rows else None


def _row_cursor(row: RowMapping) -> str:
    return encode_board_cursor(
        TeamBoardCursor(
            UUID(str(row["owning_unit_id"])),
            row["target_date"],
            UUID(str(row["ticket_id"])),
            WorkflowLeg(str(row["workflow_leg"])),
        )
    )


def _aggregate(row: RowMapping) -> TeamBoardAggregate:
    try:
        count = int(row["item_count"])
        if count < 0:
            raise ValueError
        return TeamBoardAggregate(
            UUID(str(row["owning_unit_id"])),
            str(row["unit_name"]),
            TeamBoardColumn(str(row["board_column"])),
            count if count >= 5 else None,
            count < 5,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TeamTaskBoardIntegrityError("aggregate board projection is malformed") from exc

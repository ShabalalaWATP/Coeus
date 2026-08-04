"""Representative bounded relational workloads used by the Sprint 24 gate."""

from psycopg import Connection, sql


def tree_roster(connection: Connection[object], schema: str) -> None:
    query = sql.SQL("""
      SELECT unit.id,unit.name,count(member.id) member_count
      FROM {}.closure closure JOIN {}.units unit ON unit.id=closure.descendant_id
      LEFT JOIN {}.memberships member ON member.unit_id=unit.id
      WHERE closure.ancestor_id=1 GROUP BY unit.id,unit.name
      ORDER BY unit.id LIMIT 100
    """).format(*(sql.Identifier(schema) for _ in range(3)))
    connection.execute(query).fetchall()


def board(connection: Connection[object], schema: str) -> None:
    query = sql.SQL("""
      SELECT card.id,card.unit_id,card.state,card.target_date,card.accountable_user_id
      FROM {}.cards card JOIN {}.closure closure ON closure.descendant_id=card.unit_id
      WHERE closure.ancestor_id=1 AND card.state=ANY(%s)
      ORDER BY card.unit_id,card.target_date,card.id LIMIT 100
    """).format(sql.Identifier(schema), sql.Identifier(schema))
    connection.execute(query, (["ready", "in_progress", "blocked"],)).fetchall()


def descendant_calendar_capacity(connection: Connection[object], schema: str) -> None:
    query = sql.SQL("""
      SELECT member.unit_id,count(DISTINCT member.user_id) analysts,
             sum(member.available_minutes)-coalesce(sum(event.unavailable_minutes),0) capacity
      FROM {}.closure closure
      JOIN {}.memberships member ON member.unit_id=closure.descendant_id
      LEFT JOIN {}.calendar_events event ON event.user_id=member.user_id
        AND event.starts_at<timestamptz '2026-09-01 00:00Z'
        AND event.ends_at>timestamptz '2026-08-01 00:00Z'
      WHERE closure.ancestor_id=1 GROUP BY member.unit_id ORDER BY member.unit_id
    """).format(*(sql.Identifier(schema) for _ in range(3)))
    connection.execute(query).fetchall()


def recommendation_preview(connection: Connection[object], schema: str) -> None:
    query = sql.SQL("""
      SELECT member.user_id,member.unit_id,
        member.available_minutes-coalesce(events.unavailable,0) assignable,
        coalesce(cards.active_wip,0) active_wip
      FROM {}.memberships member
      LEFT JOIN LATERAL (SELECT sum(unavailable_minutes) unavailable
        FROM {}.calendar_events event WHERE event.user_id=member.user_id
        AND event.starts_at<timestamptz '2026-09-01 00:00Z'
        AND event.ends_at>timestamptz '2026-08-01 00:00Z') events ON true
      LEFT JOIN LATERAL (SELECT count(*) active_wip FROM {}.cards card
        WHERE card.accountable_user_id=member.user_id
        AND card.state=ANY(ARRAY['ready','in_progress','blocked'])) cards ON true
      WHERE member.assignment_eligible
      ORDER BY assignable DESC,active_wip,member.user_id LIMIT 500
    """).format(*(sql.Identifier(schema) for _ in range(3)))
    rows = connection.execute(query).fetchall()
    if len(rows) != 500:
        raise RuntimeError("recommendation preview did not return 500 candidates")


def assignment_commit(connection: Connection[object], schema: str, iteration: int) -> None:
    card_id = (iteration % 500) + 1
    identifier = sql.Identifier(schema)
    with connection.transaction():
        row = connection.execute(
            sql.SQL(
                "SELECT accountable_user_id,version FROM {}.cards WHERE id=%s FOR UPDATE"
            ).format(identifier),
            (card_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("assignment card disappeared")
        connection.execute(
            sql.SQL("UPDATE {}.cards SET version=version+1 WHERE id=%s AND version=%s").format(
                identifier
            ),
            (card_id, row[1]),
        )
        connection.execute(
            sql.SQL("INSERT INTO {}.assignments(card_id,user_id) VALUES (%s,%s)").format(
                identifier
            ),
            (card_id, row[0]),
        )

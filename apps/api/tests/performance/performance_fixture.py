"""Fast, deterministic PostgreSQL fixture for Sprint 24 scale evidence."""

from psycopg import Connection, sql
from tests.performance.performance_contract import FixtureScale

DDL = """
CREATE TABLE {schema}.units (
 id integer PRIMARY KEY, parent_id integer REFERENCES {schema}.units(id), name text NOT NULL);
CREATE TABLE {schema}.closure (
 ancestor_id integer NOT NULL, descendant_id integer NOT NULL, depth integer NOT NULL,
 PRIMARY KEY (ancestor_id, descendant_id));
CREATE TABLE {schema}.memberships (
 id integer PRIMARY KEY, user_id integer NOT NULL, unit_id integer NOT NULL,
 assignment_eligible boolean NOT NULL, available_minutes integer NOT NULL);
CREATE TABLE {schema}.calendar_events (
 id integer PRIMARY KEY, user_id integer NOT NULL, unit_id integer NOT NULL,
 starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL,
 unavailable_minutes integer NOT NULL);
CREATE TABLE {schema}.cards (
 id integer PRIMARY KEY, unit_id integer NOT NULL, accountable_user_id integer NOT NULL,
 state text NOT NULL, target_date date NOT NULL, version integer NOT NULL DEFAULT 1);
CREATE TABLE {schema}.assignments (
 id bigserial PRIMARY KEY, card_id integer NOT NULL, user_id integer NOT NULL,
 committed_at timestamptz NOT NULL DEFAULT clock_timestamp());
"""

INDEXES = """
CREATE INDEX closure_ancestor_idx ON {schema}.closure(ancestor_id, depth, descendant_id);
CREATE INDEX membership_unit_idx ON {schema}.memberships(unit_id, assignment_eligible, user_id);
CREATE INDEX event_unit_window_idx ON {schema}.calendar_events(unit_id, starts_at, ends_at);
CREATE INDEX event_user_window_idx ON {schema}.calendar_events(user_id, starts_at, ends_at);
CREATE INDEX card_unit_state_idx ON {schema}.cards(unit_id, state, target_date, id);
CREATE INDEX card_user_state_idx ON {schema}.cards(accountable_user_id, state);
"""


def create_fixture(connection: Connection[object], schema: str, scale: FixtureScale) -> None:
    scale.validate()
    identifier = sql.Identifier(schema)
    connection.execute(sql.SQL("CREATE SCHEMA {}").format(identifier))
    connection.execute(sql.SQL(DDL).format(schema=identifier))
    connection.execute(
        sql.SQL("""
        INSERT INTO {}.units(id,parent_id,name)
        SELECT id,CASE WHEN id=1 THEN NULL ELSE ((id-2)/10)+1 END,'Unit '||id
        FROM generate_series(1,%s) id
        """).format(identifier),
        (scale.units,),
    )
    connection.execute(
        sql.SQL("""
        WITH RECURSIVE lineage AS (
          SELECT id ancestor_id,id descendant_id,0 depth FROM {}.units
          UNION ALL
          SELECT lineage.ancestor_id,child.id,lineage.depth+1
          FROM lineage JOIN {}.units child ON child.parent_id=lineage.descendant_id
        ) INSERT INTO {}.closure SELECT * FROM lineage
        """).format(identifier, identifier, identifier)
    )
    connection.execute(
        sql.SQL("""
        INSERT INTO {}.memberships(id,user_id,unit_id,assignment_eligible,available_minutes)
        SELECT id,id,mod(id-1,%s)+1,true,2400-mod(id,480)
        FROM generate_series(1,%s) id
        """).format(identifier),
        (scale.units, scale.memberships),
    )
    connection.execute(
        sql.SQL("""
        INSERT INTO {}.calendar_events(id,user_id,unit_id,starts_at,ends_at,unavailable_minutes)
        SELECT id,mod(id-1,%s)+1,mod(id-1,%s)+1,
          timestamptz '2026-08-01 08:00Z'+((mod(id,31))||' days')::interval,
          timestamptz '2026-08-01 09:00Z'+((mod(id,31))||' days')::interval,60
        FROM generate_series(1,%s) id
        """).format(identifier),
        (scale.memberships, scale.units, scale.calendar_events),
    )
    connection.execute(
        sql.SQL("""
        INSERT INTO {}.cards(id,unit_id,accountable_user_id,state,target_date)
        SELECT id,mod(id-1,%s)+1,mod(id-1,%s)+1,
          (ARRAY['ready','in_progress','blocked'])[1+mod(id,3)],
          date '2026-08-01'+mod(id,31)
        FROM generate_series(1,%s) id
        """).format(identifier),
        (scale.units, scale.memberships, scale.active_cards),
    )
    connection.execute(sql.SQL(INDEXES).format(schema=identifier))
    for name in ("units", "closure", "memberships", "calendar_events", "cards"):
        connection.execute(sql.SQL("ANALYSE {}.{}").format(identifier, sql.Identifier(name)))
    connection.commit()


def cardinalities(connection: Connection[object], schema: str) -> dict[str, int]:
    identifier = sql.Identifier(schema)
    names = ("units", "memberships", "calendar_events", "cards")
    values = {}
    for name in names:
        count = connection.execute(
            sql.SQL("SELECT count(*) FROM {}.{}").format(identifier, sql.Identifier(name))
        ).fetchone()
        values["active_cards" if name == "cards" else name] = int(count[0])
    values["candidates"] = 500
    return values

"""Cross-unit handover requests do not expose package lifecycle state."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.work_package_handovers import WorkPackageHandoverDenied
from coeus.persistence.work_package_handovers_postgres import (
    PostgresWorkPackageHandoverStore,
)
from postgres.work_package_handover_support import (
    insert_handover_evidence,
    upgrade_handover_schema,
)

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("package_state", ("absent", "current", "stale", "already-target"))
def test_valid_sibling_grant_cannot_distinguish_package_state(
    postgres_database_url: str, package_state: str
) -> None:
    upgrade_handover_schema(postgres_database_url)
    evidence = insert_handover_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    request = evidence.request
    if package_state == "absent":
        request = replace(request, package_id=uuid4())
    else:
        sibling_id = uuid4()
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO organisation_units(unit_id,name,short_name,category,is_active,"
                    "valid_from,time_zone,description,provenance,version) VALUES "
                    "(:unit,'Sibling Team','SIB','command',true,:now,'Europe/London','',"
                    "'synthetic-test',1)"
                ),
                {"unit": sibling_id, "now": datetime.now(UTC)},
            )
            connection.execute(
                text(
                    "INSERT INTO organisation_unit_closure"
                    "(ancestor_unit_id,descendant_unit_id,depth) VALUES (:unit,:unit,0)"
                ),
                {"unit": sibling_id},
            )
            connection.execute(
                text(
                    "UPDATE canonical_work_packages SET owning_unit_id=:unit,"
                    "accountable_user_id=CASE WHEN :already THEN :target "
                    "ELSE accountable_user_id END "
                    "WHERE package_id=:package"
                ),
                {
                    "unit": sibling_id,
                    "already": package_state == "already-target",
                    "target": evidence.target_id,
                    "package": evidence.package_id,
                },
            )
            connection.execute(
                text(
                    "UPDATE team_task_ownership SET owning_unit_id=:unit "
                    "WHERE ticket_id=:ticket AND workflow_leg='rfa'"
                ),
                {
                    "unit": sibling_id,
                    "ticket": evidence.ticket.ticket_id,
                },
            )
        if package_state == "stale":
            request = replace(request, expected_package_version=999)

    with pytest.raises(WorkPackageHandoverDenied) as denied:
        PostgresWorkPackageHandoverStore(engine).preview(evidence.actor_id, request)
    assert str(denied.value) == "work package is unavailable"
    engine.dispose()

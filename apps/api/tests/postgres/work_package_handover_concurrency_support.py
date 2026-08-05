"""Concurrency fixture helpers for accountable-owner handover."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Engine, text

from coeus.domain.work_package_handovers import ReservationHandover
from postgres.work_package_handover_support import HandoverEvidence


def clone_handover_package(engine: Engine, evidence: HandoverEvidence):  # type: ignore[no-untyped-def]
    package_id, reservation_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    with engine.begin() as connection:
        source = connection.execute(
            text(
                "SELECT package.ticket_id,package.owning_unit_id,reservation.starts_at,"
                "reservation.ends_at,reservation.reserved_minutes "
                "FROM canonical_work_packages package JOIN capacity_reservations reservation "
                "ON reservation.reservation_id=:reservation "
                "WHERE package.package_id=:package"
            ),
            {"package": evidence.package_id, "reservation": evidence.reservation_id},
        ).one()
        connection.execute(
            text(
                "INSERT INTO canonical_work_packages"
                "(package_id,ticket_id,workflow_leg,owning_unit_id,accountable_user_id,title,state,"
                "estimated_minutes,remaining_minutes,sort_order,version,provenance,created_at,"
                "updated_at) VALUES (:package,:ticket,'rfa',:unit,:owner,'Second handover',"
                "'ready',240,240,2,1,'test',:now,:now)"
            ),
            {
                "package": package_id,
                "ticket": source.ticket_id,
                "unit": source.owning_unit_id,
                "owner": evidence.owner_id,
                "now": now,
            },
        )
        connection.execute(
            text(
                "INSERT INTO work_package_participants"
                "(package_id,user_id,role,active,created_at) "
                "VALUES (:package,:owner,'accountable',true,:now)"
            ),
            {"package": package_id, "owner": evidence.owner_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO capacity_reservations"
                "(reservation_id,user_id,ticket_id,workflow_leg,package_id,starts_at,ends_at,"
                "reserved_minutes,state,idempotency_key,request_hash,actor_user_id,version,"
                "created_at,updated_at) VALUES "
                "(:reservation,:owner,:ticket,'rfa',:package,:start,:end,:minutes,'active',"
                ":key,:hash,:actor,1,:now,:now)"
            ),
            {
                "reservation": reservation_id,
                "owner": evidence.owner_id,
                "ticket": source.ticket_id,
                "package": package_id,
                "start": source.starts_at,
                "end": source.ends_at,
                "minutes": source.reserved_minutes,
                "key": f"source-{reservation_id}",
                "hash": "e" * 64,
                "actor": evidence.actor_id,
                "now": now,
            },
        )
    item = evidence.request.reservations[0]
    return replace(
        evidence.request,
        package_id=package_id,
        reservations=(
            ReservationHandover(
                reservation_id,
                1,
                item.disposition,
                uuid4(),
                f"replacement-{reservation_id}",
            ),
        ),
    )


def add_authorised_actor(engine: Engine, evidence: HandoverEvidence) -> tuple[UUID, UUID]:
    actor_id, grant_id = uuid4(), uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO identity_account_projection"
                "(user_id,is_active,roles,credential_version,source_hash) "
                "VALUES (:actor,true,ARRAY['Administrator'],1,:hash)"
            ),
            {"actor": actor_id, "hash": "f" * 64},
        )
        connection.execute(
            text(
                "INSERT INTO team_management_grants"
                "(grant_id,manager_user_id,root_unit_id,action,include_descendants,valid_from,"
                "created_by_user_id,reason,version) VALUES "
                "(:grant,:actor,:unit,'task:assign',false,transaction_timestamp(),:actor,"
                "'Concurrent handover grant',1)"
            ),
            {"grant": grant_id, "actor": actor_id, "unit": evidence.unit_id},
        )
    return actor_id, grant_id

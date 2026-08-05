"""Bounded synthetic rows for the integrated workspace operations tests."""

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine


def seed_authority(
    engine: Engine, actor: UUID, unit_id: UUID, actions: Iterable[str]
) -> dict[str, UUID]:
    now, grants = datetime.now(UTC), {}
    with engine.begin() as connection:
        for action in actions:
            grant_id = uuid4()
            grants[action] = grant_id
            connection.execute(
                text(
                    "INSERT INTO team_management_grants"
                    "(grant_id,manager_user_id,root_unit_id,action,include_descendants,"
                    "valid_from,created_by_user_id,reason,delegation_depth,version) VALUES "
                    "(:grant,:actor,:unit,:action,true,:at,:actor,'Synthetic authority.',0,1)"
                ),
                {"grant": grant_id, "actor": actor, "unit": unit_id, "action": action, "at": now},
            )
    return grants


def seed_delivery_profile(engine: Engine, unit_id: UUID, capabilities: Iterable[str]) -> UUID:
    profile_id, now = uuid4(), datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO team_delivery_profiles"
                "(profile_id,unit_id,route,wip_limit,weekly_hours,policy_version,"
                "is_active,provenance) VALUES (:profile,:unit,'rfa',4,40,1,true,'test')"
            ),
            {"profile": profile_id, "unit": unit_id},
        )
        for capability_id in capabilities:
            connection.execute(
                text(
                    "INSERT INTO team_capability_coverage"
                    "(coverage_id,profile_id,capability_id,proficiency,valid_from,"
                    "policy_version,approved_by_user_id) VALUES "
                    "(:coverage,:profile,:capability,3,:at,1,:actor)"
                ),
                {
                    "coverage": uuid4(),
                    "profile": profile_id,
                    "capability": capability_id,
                    "at": now,
                    "actor": uuid4(),
                },
            )
    return profile_id


def seed_membership(engine: Engine, user_id: UUID, unit_id: UUID) -> UUID:
    membership_id, now = uuid4(), datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO team_memberships(membership_id,user_id,unit_id,role,state,"
                "assignment_eligible,valid_from,created_by_user_id,reason,provenance,version) "
                "VALUES (:membership,:user,:unit,'member','active',true,:at,:user,"
                "'Synthetic posting.','test',1)"
            ),
            {"membership": membership_id, "user": user_id, "unit": unit_id, "at": now},
        )
    return membership_id


def seed_work_package(engine: Engine, unit_id: UUID, title: str) -> UUID:
    package_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO canonical_work_packages("
                "package_id,ticket_id,workflow_leg,owning_unit_id,accountable_user_id,"
                "title,state,sort_order,version,provenance,created_at,updated_at) VALUES ("
                # 'pending' is the only open state that may hold no owner.
                ":package,:ticket,'rfa',:unit,NULL,:title,'pending',0,1,'test',"
                "transaction_timestamp(),transaction_timestamp())"
            ),
            {"package": package_id, "ticket": uuid4(), "unit": unit_id, "title": title},
        )
    return package_id


def seed_store_link(engine: Engine, owner_id: UUID, unit_id: UUID, label: str) -> UUID:
    link_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workspace_store_links("
                "link_id,owner_user_id,unit_id,source_type,source_id,target_type,target_id,"
                "label,version,created_at,updated_at) VALUES "
                "(:link,:owner,:unit,'ticket',:source,'product',:target,:label,1,now(),now())"
            ),
            {
                "link": link_id,
                "owner": owner_id,
                "unit": unit_id,
                "source": uuid4(),
                "target": uuid4(),
                "label": label,
            },
        )
    return link_id

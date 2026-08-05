"""Shared builders for PostgreSQL organisation merge evidence."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import Engine, text

from coeus.domain.organisation import (
    DeliveryRoute,
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationManagementGrant,
    TeamCapabilityCoverage,
    TeamDeliveryProfile,
    TeamMembership,
)
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationOperation,
    OrganisationMutationRequest,
)
from coeus.domain.organisation_merge import (
    MergeDisposition,
    MergeDispositionAction,
    MergeRecordKind,
    MergeUnitAuthority,
    MergeUnitVersion,
    OrganisationMergeImpact,
    OrganisationMergePlan,
    OrganisationMergeRequest,
)
from coeus.domain.team_task_ownership import (
    TeamTaskOwnership,
    TeamTaskOwnershipState,
    WorkflowLeg,
)
from coeus.persistence.organisation_bootstrap_postgres import (
    PostgresOrganisationBootstrapStore,
)
from coeus.persistence.organisation_lifecycle_postgres import (
    PostgresOrganisationMutationStore,
)
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.persistence.team_task_ownership_postgres import (
    PostgresTeamTaskOwnershipRepository,
)
from coeus.services.organisation_lifecycle import OrganisationLifecycleService

API_ROOT = Path(__file__).resolve().parents[2]


def upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def grant_id(engine: Engine, action: ManagementAction) -> UUID:
    with engine.connect() as connection:
        return UUID(
            str(
                connection.execute(
                    text("SELECT grant_id FROM team_management_grants WHERE action=:action"),
                    {"action": action.value},
                ).scalar_one()
            )
        )


def foundation(database_url: str):  # type: ignore[no-untyped-def]
    from sqlalchemy import create_engine

    engine = create_engine(database_url)
    actor_id, root_id = uuid4(), uuid4()
    PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(),
            actor_id,
            root_id,
            "Synthetic Defence Intelligence",
            "Synthetic DI",
            "Europe/London",
            "Synthetic hierarchy root.",
        )
    )
    activate_principals(engine, actor_id)
    repository = PostgresOrganisationRepository(engine)
    lifecycle = OrganisationLifecycleService(repository, PostgresOrganisationMutationStore(engine))
    return engine, repository, lifecycle, actor_id, root_id


def create_unit(  # type: ignore[no-untyped-def]
    engine, repository, lifecycle, actor_id, parent_id, name
):
    parent = repository.get_unit(parent_id)
    assert parent is not None
    unit_id = uuid4()
    request = OrganisationMutationRequest(
        OrganisationMutationOperation.CREATE,
        unit_id,
        parent_id,
        parent.version,
        name,
        name[:12],
        OrganisationCategory.DELIVERY_TEAM,
        "Europe/London",
        f"Synthetic {name} unit.",
        grant_id(engine, ManagementAction.ORGANISATION_CREATE),
        f"Create synthetic {name}.",
    )
    preview = lifecycle.preview(request, actor_id)
    lifecycle.execute(
        OrganisationMutationCommand(
            uuid4(),
            f"create-{name.casefold().replace(' ', '-')}",
            actor_id,
            request,
            preview.preview_hash,
        )
    )
    return unit_id


def seed_dependencies(  # type: ignore[no-untyped-def]
    engine, repository, actor_id, first_id, second_id, successor_id
):
    now = datetime.now(UTC) - timedelta(minutes=1)
    user_id, membership_id = uuid4(), uuid4()
    repository.upsert_membership(
        TeamMembership(
            membership_id,
            user_id,
            first_id,
            MembershipRole.MEMBER,
            MembershipState.ACTIVE,
            True,
            now,
            actor_id,
            "Synthetic source posting.",
            "synthetic-test",
        )
    )
    ended_user_id = uuid4()
    repository.upsert_membership(
        TeamMembership(
            uuid4(),
            ended_user_id,
            second_id,
            MembershipRole.MEMBER,
            MembershipState.ACTIVE,
            False,
            now,
            actor_id,
            "Synthetic posting to end.",
            "synthetic-test",
        )
    )
    profile_id = uuid4()
    repository.upsert_delivery_profile(
        TeamDeliveryProfile(profile_id, first_id, DeliveryRoute.RFA, 6, 37.5)
    )
    coverage_id = uuid4()
    repository.upsert_capability_coverage(
        TeamCapabilityCoverage(coverage_id, profile_id, "synthetic-osint", 4, now, actor_id)
    )
    direct_grant_id = uuid4()
    repository.upsert_management_grant(
        OrganisationManagementGrant(
            direct_grant_id,
            uuid4(),
            first_id,
            ManagementAction.TASK_ASSIGN,
            False,
            now,
            actor_id,
            "Synthetic source-only task authority.",
        )
    )
    with engine.connect() as connection:
        revision_id = UUID(
            str(
                connection.execute(
                    text(
                        "SELECT revision_id FROM organisation_topology_revisions "
                        "WHERE unit_id=:unit_id ORDER BY valid_from DESC LIMIT 1"
                    ),
                    {"unit_id": second_id},
                ).scalar_one()
            )
        )
    ownership = TeamTaskOwnership(
        uuid4(),
        uuid4(),
        WorkflowLeg.RFA,
        second_id,
        None,
        TeamTaskOwnershipState.TRIAGE,
        revision_id,
        1,
        1,
        uuid4(),
        "synthetic-test",
        now,
    )
    PostgresTeamTaskOwnershipRepository(engine).save_ownership(ownership, expected_version=None)
    transfer_id = pending_transfer(
        engine, actor_id, membership_id, user_id, first_id, successor_id, now
    )
    return (
        user_id,
        ended_user_id,
        membership_id,
        profile_id,
        coverage_id,
        direct_grant_id,
        transfer_id,
        ownership,
    )


def merge_request(  # type: ignore[no-untyped-def]
    engine, repository, source_ids, successor_id
) -> OrganisationMergeRequest:
    units = tuple(repository.get_unit(item) for item in (*source_ids, successor_id))
    assert all(item is not None for item in units)
    versions = tuple(MergeUnitVersion(item.unit_id, item.version) for item in units if item)
    authority = grant_id(engine, ManagementAction.ORGANISATION_RESTRUCTURE)
    return OrganisationMergeRequest(
        versions[:-1],
        versions[-1],
        tuple(MergeUnitAuthority(item.unit_id, authority) for item in versions),
        "Merge the synthetic delivery teams.",
    )


def merge_plan(
    request: OrganisationMergeRequest, impact: OrganisationMergeImpact
) -> OrganisationMergePlan:
    successor_id = request.successor.unit_id
    dispositions = []
    for item in impact.records:
        if (
            item.kind is MergeRecordKind.MEMBERSHIP
            and item.source_unit_id == request.sources[0].unit_id
        ):
            action, target, replacement = MergeDispositionAction.MOVE, successor_id, uuid4()
        elif item.kind is MergeRecordKind.MEMBERSHIP:
            action, target, replacement = MergeDispositionAction.END, None, None
        elif item.kind in {
            MergeRecordKind.CHILD_UNIT,
            MergeRecordKind.DELIVERY_PROFILE,
            MergeRecordKind.CAPABILITY,
            MergeRecordKind.TASK,
        }:
            action, target, replacement = MergeDispositionAction.MOVE, successor_id, None
        elif item.kind is MergeRecordKind.GRANT:
            action, target, replacement = MergeDispositionAction.REVOKE, None, None
        else:
            action, target, replacement = MergeDispositionAction.CANCEL, None, None
        dispositions.append(
            MergeDisposition(item.kind, item.record_id, item.version, action, target, replacement)
        )
    return OrganisationMergePlan(request, tuple(dispositions))


def pending_transfer(
    engine: Engine,
    actor_id: UUID,
    membership_id: UUID,
    user_id: UUID,
    source_id: UUID,
    target_id: UUID,
    now: datetime,
) -> UUID:
    transfer_id = uuid4()
    transfer_grant_id = grant_id(engine, ManagementAction.ROSTER_TRANSFER)
    with engine.begin() as connection:
        connection.execute(
            text(_INSERT_TRANSFER),
            {
                "command_id": transfer_id,
                "key": f"pending-merge-{transfer_id}",
                "request_hash": "a" * 64,
                "reason_hash": "b" * 64,
                "actor_id": actor_id,
                "membership_id": membership_id,
                "target_membership_id": uuid4(),
                "user_id": user_id,
                "source_id": source_id,
                "target_id": target_id,
                "effective_at": now + timedelta(days=1),
                "grant_id": transfer_grant_id,
                "now": now,
            },
        )
    return transfer_id


_INSERT_TRANSFER = """
INSERT INTO organisation_personnel_transfers(command_id,idempotency_key,request_hash,reason_hash,
 reason,actor_user_id,source_membership_id,target_membership_id,user_id,source_unit_id,
 target_unit_id,expected_membership_version,expected_target_unit_version,target_role,
 assignment_eligible,effective_at,source_authorising_grant_id,target_authorising_grant_id,
 status,source_result_version,target_result_version,failure_code,scheduled_at,applied_at)
VALUES (:command_id,:key,:request_hash,:reason_hash,'Synthetic pending transfer.',:actor_id,
 :membership_id,:target_membership_id,:user_id,:source_id,:target_id,1,1,'member',true,
 :effective_at,:grant_id,:grant_id,'pending',1,0,'',:now,NULL)
"""

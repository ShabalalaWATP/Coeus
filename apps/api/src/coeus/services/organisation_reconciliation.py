"""Idempotent shadow backfill from the legacy flat-team authority."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.application.ports.organisation_reconciliation import (
    OrganisationReconciliationCommitter,
)
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.organisation import (
    DeliveryRoute,
    FindingSeverity,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationReconciliationCheckpoint,
    OrganisationReconciliationFinding,
    OrganisationTopologyRevision,
    OrganisationUnit,
    ReconciliationStatus,
    TeamCapabilityCoverage,
    TeamDeliveryProfile,
    TeamMembership,
)
from coeus.domain.organisation_reconciliation import (
    PROJECTION_ACTOR_ID,
    OrganisationReconciliationPlan,
)
from coeus.domain.teams import OrgTeam, TeamKind

SOURCE_NAMESPACE = "legacy-flat-teams-v1"


@dataclass(frozen=True)
class OrganisationReconciliationResult:
    checkpoint_id: UUID
    source_digest: str
    units_written: int
    memberships_written: int
    blocking_findings: int


class OrganisationReconciliationService:
    """Project flat teams without inventing a home for ambiguous people."""

    def __init__(self, organisation: OrganisationReconciliationCommitter) -> None:
        self._organisation = organisation

    def reconcile(
        self,
        *,
        teams: tuple[OrgTeam, ...],
        users: tuple[UserAccount, ...],
        actor_user_id: UUID,
        effective_at: datetime,
    ) -> OrganisationReconciliationResult:
        digest = _source_digest(teams, users)
        checkpoint_id = _stable_id("checkpoint", digest)
        units, profiles, coverage = _team_projections(teams, PROJECTION_ACTOR_ID)
        memberships, findings = _people_projections(
            teams, users, checkpoint_id, PROJECTION_ACTOR_ID, effective_at
        )
        checkpoint = OrganisationReconciliationCheckpoint(
            checkpoint_id=checkpoint_id,
            source_namespace=SOURCE_NAMESPACE,
            source_digest=digest,
            status=ReconciliationStatus.COMPLETED,
            started_at=effective_at,
            completed_at=effective_at,
            cursor={
                "team_count": len(teams),
                "units_written": len(units),
                "memberships_written": len(memberships),
                "blocking_findings": len(findings),
            },
        )
        self._organisation.apply_reconciliation(
            OrganisationReconciliationPlan(
                checkpoint,
                actor_user_id,
                effective_at,
                units,
                profiles,
                coverage,
                memberships,
                findings,
            )
        )
        return OrganisationReconciliationResult(
            checkpoint_id,
            digest,
            len(units),
            len(memberships),
            len(findings),
        )


def _team_projection(
    team: OrgTeam, actor_id: UUID
) -> tuple[
    tuple[OrganisationUnit, OrganisationTopologyRevision],
    TeamDeliveryProfile,
    TeamCapabilityCoverage | None,
]:
    category = (
        OrganisationCategory.DELIVERY_TEAM
        if team.kind in {TeamKind.RFA, TeamKind.CM}
        else OrganisationCategory.GOVERNANCE_TEAM
    )
    unit = OrganisationUnit(
        unit_id=team.team_id,
        name=team.name,
        short_name=team.name[:32].rstrip(),
        category=category,
        parent_unit_id=None,
        valid_from=team.created_at,
        is_active=team.is_active,
        description="Migrated from the legacy flat-team authority.",
        provenance=SOURCE_NAMESPACE,
    )
    revision = OrganisationTopologyRevision(
        revision_id=_stable_id("revision", str(team.team_id)),
        unit_id=team.team_id,
        parent_unit_id=None,
        path=(team.team_id,),
        valid_from=team.created_at,
        change_command_id=_stable_id("backfill-command", str(team.team_id)),
        changed_by_user_id=actor_id,
    )
    profile_id = _stable_id("delivery-profile", str(team.team_id))
    profile = TeamDeliveryProfile(
        profile_id=profile_id,
        unit_id=team.team_id,
        route=DeliveryRoute(team.kind.value),
        wip_limit=5,
        weekly_hours=37.0,
        is_active=team.is_active,
        provenance=SOURCE_NAMESPACE,
    )
    coverage = (
        TeamCapabilityCoverage(
            coverage_id=_stable_id("capability", str(team.team_id), team.capability_team_id),
            profile_id=profile_id,
            capability_id=team.capability_team_id,
            proficiency=3,
            valid_from=team.created_at,
            approved_by_user_id=actor_id,
        )
        if team.capability_team_id
        else None
    )
    return (unit, revision), profile, coverage


def _team_projections(
    teams: tuple[OrgTeam, ...], actor_id: UUID
) -> tuple[
    tuple[tuple[OrganisationUnit, OrganisationTopologyRevision], ...],
    tuple[TeamDeliveryProfile, ...],
    tuple[TeamCapabilityCoverage, ...],
]:
    projected = tuple(
        _team_projection(team, actor_id)
        for team in sorted(teams, key=lambda item: str(item.team_id))
    )
    return (
        tuple(item[0] for item in projected),
        tuple(item[1] for item in projected),
        tuple(item[2] for item in projected if item[2] is not None),
    )


def _finding(
    checkpoint_id: UUID,
    code: str,
    user_id: UUID,
    details: dict[str, object],
    created_at: datetime,
) -> OrganisationReconciliationFinding:
    source_identifier = str(user_id)
    return OrganisationReconciliationFinding(
        finding_id=_stable_id(str(checkpoint_id), code, source_identifier),
        checkpoint_id=checkpoint_id,
        finding_code=code,
        severity=FindingSeverity.BLOCKING,
        source_identifier=source_identifier,
        details=details,
        created_at=created_at,
    )


def _people_projections(
    teams: tuple[OrgTeam, ...],
    users: tuple[UserAccount, ...],
    checkpoint_id: UUID,
    actor_id: UUID,
    effective_at: datetime,
) -> tuple[tuple[TeamMembership, ...], tuple[OrganisationReconciliationFinding, ...]]:
    memberships: list[TeamMembership] = []
    findings: list[OrganisationReconciliationFinding] = []
    users_by_id = {user.user_id: user for user in users}
    for user_id, postings in sorted(
        _membership_evidence(teams).items(), key=lambda item: str(item[0])
    ):
        if len(postings) > 1:
            findings.append(
                _finding(
                    checkpoint_id,
                    "overlapping_legacy_membership",
                    user_id,
                    {"team_ids": sorted(str(team_id) for team_id in postings)},
                    effective_at,
                )
            )
            continue
        user = users_by_id.get(user_id)
        team_id, role = next(iter(postings.items()))
        if user is None:
            findings.append(
                _finding(
                    checkpoint_id,
                    "legacy_member_not_found",
                    user_id,
                    {"team_id": str(team_id)},
                    effective_at,
                )
            )
            continue
        memberships.append(
            _membership(
                user,
                team_id,
                role,
                actor_id,
                effective_at,
                _team_active(teams, team_id),
            )
        )
    return tuple(memberships), tuple(findings)


def _membership_evidence(
    teams: tuple[OrgTeam, ...],
) -> dict[UUID, dict[UUID, MembershipRole]]:
    evidence: dict[UUID, dict[UUID, MembershipRole]] = defaultdict(dict)
    for team in teams:
        for user_id in team.member_user_ids:
            evidence[user_id][team.team_id] = MembershipRole.MEMBER
        for user_id in team.manager_user_ids:
            evidence[user_id][team.team_id] = MembershipRole.MANAGER
    return dict(evidence)


def _membership(
    user: UserAccount,
    team_id: UUID,
    role: MembershipRole,
    actor_id: UUID,
    valid_from: datetime,
    team_active: bool,
) -> TeamMembership:
    active = user.is_active and team_active
    analyst = RoleName.INTELLIGENCE_ANALYST in user.roles
    return TeamMembership(
        membership_id=_stable_id("membership", str(user.user_id), str(team_id)),
        user_id=user.user_id,
        unit_id=team_id,
        role=role,
        state=MembershipState.ACTIVE if active else MembershipState.SUSPENDED,
        assignment_eligible=active and analyst and role is MembershipRole.MEMBER,
        valid_from=valid_from,
        created_by_user_id=actor_id,
        reason="Backfilled from the legacy flat-team authority.",
        provenance=SOURCE_NAMESPACE,
    )


def _source_digest(teams: tuple[OrgTeam, ...], users: tuple[UserAccount, ...]) -> str:
    referenced_user_ids = {
        user_id for team in teams for user_id in (*team.manager_user_ids, *team.member_user_ids)
    }
    payload = {
        "teams": [
            {
                "team_id": str(team.team_id),
                "name": team.name,
                "kind": team.kind.value,
                "managers": sorted(str(value) for value in team.manager_user_ids),
                "members": sorted(str(value) for value in team.member_user_ids),
                "capability_team_id": team.capability_team_id,
                "is_active": team.is_active,
                "created_at": team.created_at.isoformat(),
            }
            for team in sorted(teams, key=lambda item: str(item.team_id))
        ],
        "users": [
            {
                "user_id": str(user.user_id),
                "is_active": user.is_active,
                "roles": sorted(role.value for role in user.roles),
            }
            for user in sorted(users, key=lambda item: str(item.user_id))
            if user.user_id in referenced_user_ids
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _stable_id(*parts: str) -> UUID:
    return uuid5(NAMESPACE_URL, ":".join(("coeus-organisation-v1", *parts)))


def _team_active(teams: tuple[OrgTeam, ...], team_id: UUID) -> bool:
    return next(team.is_active for team in teams if team.team_id == team_id)

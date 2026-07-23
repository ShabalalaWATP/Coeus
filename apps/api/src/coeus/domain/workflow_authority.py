"""Commit-time authority expectations for protected workflow writes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from coeus.core.permissions import Permission
from coeus.domain.access import (
    AccessControlGroup,
    AccessControlGroupMembership,
    ProductStatus,
)
from coeus.domain.auth import SessionRecord, UserAccount
from coeus.domain.teams import OrgTeam, TeamKind, team_member_ids


class WorkflowCommitResult(StrEnum):
    COMMITTED = "committed"
    TICKET_CHANGED = "ticket_changed"
    AUTHORITY_REVOKED = "authority_revoked"


@dataclass(frozen=True)
class WorkflowProductVisibility:
    """Current product facts needed to recheck RFI offer visibility."""

    product_id: UUID
    status: ProductStatus
    classification_level: int
    acg_ids: frozenset[UUID]


@dataclass(frozen=True)
class RfiCommitAuthority:
    """Requester scope and all product evidence persisted by one RFI retrieval."""

    expected_requester: UserAccount
    expected_active_acg_ids: frozenset[UUID]
    persisted_product_ids: frozenset[UUID]


@dataclass(frozen=True)
class QcCommitAuthority:
    """Mutable QC eligibility and product access facts captured before release."""

    draft_classification_level: int
    draft_acg_ids: frozenset[UUID]
    release_classification_level: int
    release_acg_ids: frozenset[UUID]
    expected_recipient: UserAccount | None


@dataclass(frozen=True)
class WorkflowCommitAuthority:
    """Exact principal state and mutable relationships required at commit."""

    expected_actor: UserAccount
    expected_session: SessionRecord | None
    required_permissions: frozenset[Permission]
    rfi: RfiCommitAuthority | None = None
    qc: QcCommitAuthority | None = None


def workflow_authority_result(
    users: tuple[UserAccount, ...],
    sessions: tuple[SessionRecord, ...],
    acgs: tuple[AccessControlGroup, ...],
    memberships: tuple[AccessControlGroupMembership, ...],
    teams: tuple[OrgTeam, ...],
    products: tuple[WorkflowProductVisibility, ...],
    authority: WorkflowCommitAuthority,
    *,
    now: datetime | None = None,
) -> WorkflowCommitResult:
    """Evaluate one captured authority set against live locked state."""
    current_actor = _user(users, authority.expected_actor.user_id)
    if (
        current_actor is None
        or current_actor != authority.expected_actor
        or not current_actor.is_active
        or not authority.required_permissions.issubset(current_actor.permissions)
        or not _session_is_current(sessions, authority, now or datetime.now(UTC))
        or not _rfi_is_current(users, acgs, memberships, products, authority.rfi)
        or not _qc_is_current(users, acgs, memberships, teams, current_actor, authority.qc)
    ):
        return WorkflowCommitResult.AUTHORITY_REVOKED
    return WorkflowCommitResult.COMMITTED


def _session_is_current(
    sessions: tuple[SessionRecord, ...],
    authority: WorkflowCommitAuthority,
    now: datetime,
) -> bool:
    expected = authority.expected_session
    if expected is None:
        return True
    current = next(
        (session for session in sessions if session.session_id == expected.session_id),
        None,
    )
    return bool(
        current == expected
        and current is not None
        and current.user_id == authority.expected_actor.user_id
        and current.credential_version == authority.expected_actor.credential_version
        and current.expires_at > now
    )


def _rfi_is_current(
    users: tuple[UserAccount, ...],
    acgs: tuple[AccessControlGroup, ...],
    memberships: tuple[AccessControlGroupMembership, ...],
    products: tuple[WorkflowProductVisibility, ...],
    authority: RfiCommitAuthority | None,
) -> bool:
    if authority is None:
        return True
    requester = _user(users, authority.expected_requester.user_id)
    active_acgs = _active_acg_ids(acgs, memberships, authority.expected_requester.user_id)
    if (
        requester != authority.expected_requester
        or active_acgs != authority.expected_active_acg_ids
    ):
        return False
    current_products = {product.product_id: product for product in products}
    return all(
        _can_read_product(requester, active_acgs, current_products.get(product_id))
        for product_id in authority.persisted_product_ids
    )


def _qc_is_current(
    users: tuple[UserAccount, ...],
    acgs: tuple[AccessControlGroup, ...],
    memberships: tuple[AccessControlGroupMembership, ...],
    teams: tuple[OrgTeam, ...],
    actor: UserAccount,
    authority: QcCommitAuthority | None,
) -> bool:
    if authority is None:
        return True
    actor_acgs = _active_acg_ids(acgs, memberships, actor.user_id)
    active_acg_ids = frozenset(acg.acg_id for acg in acgs if acg.is_active)
    team_eligible = any(
        team.is_active and team.kind == TeamKind.QC and actor.user_id in team_member_ids(team)
        for team in teams
    )
    draft_visible = bool(
        Permission.PRODUCT_READ in actor.permissions
        and actor.clearance_level >= authority.draft_classification_level
        and (not authority.draft_acg_ids or actor_acgs.intersection(authority.draft_acg_ids))
    )
    release_acgs_valid = authority.release_acg_ids.issubset(active_acg_ids) and bool(
        Permission.PRODUCT_READ_RESTRICTED in actor.permissions
        or authority.release_acg_ids.issubset(actor_acgs)
    )
    recipient = authority.expected_recipient
    recipient_visible = True
    if recipient is not None:
        current = _user(users, recipient.user_id)
        recipient_acgs = _active_acg_ids(acgs, memberships, recipient.user_id)
        recipient_visible = current == recipient and _can_read_release(
            current,
            recipient_acgs,
            authority.release_classification_level,
            authority.release_acg_ids,
        )
    return team_eligible and draft_visible and release_acgs_valid and recipient_visible


def _user(users: tuple[UserAccount, ...], user_id: UUID) -> UserAccount | None:
    return next((user for user in users if user.user_id == user_id), None)


def _active_acg_ids(
    acgs: tuple[AccessControlGroup, ...],
    memberships: tuple[AccessControlGroupMembership, ...],
    user_id: UUID,
) -> frozenset[UUID]:
    active = frozenset(acg.acg_id for acg in acgs if acg.is_active)
    return frozenset(
        membership.acg_id
        for membership in memberships
        if membership.user_id == user_id and membership.acg_id in active
    )


def _can_read_product(
    user: UserAccount | None,
    active_acgs: frozenset[UUID],
    product: WorkflowProductVisibility | None,
) -> bool:
    return bool(
        user is not None
        and user.is_active
        and Permission.PRODUCT_READ in user.permissions
        and product is not None
        and product.status == ProductStatus.PUBLISHED
        and user.clearance_level >= product.classification_level
        and active_acgs.intersection(product.acg_ids)
    )


def _can_read_release(
    user: UserAccount | None,
    active_acgs: frozenset[UUID],
    classification_level: int,
    product_acgs: frozenset[UUID],
) -> bool:
    return bool(
        user is not None
        and user.is_active
        and Permission.PRODUCT_READ in user.permissions
        and user.clearance_level >= classification_level
        and active_acgs.intersection(product_acgs)
    )

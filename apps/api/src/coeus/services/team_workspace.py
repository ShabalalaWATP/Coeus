"""Team rosters, membership management and member profiles.

Object-level rules: a team is visible only to its own managers and members
(administrators see all); membership changes require TEAM_MANAGE *and*
management of that specific team; profiles are self-edited and readable by
teammates.
"""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.teams import OrgTeam, UserProfile, team_member_ids
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.teams import TeamRepository
from coeus.services.audit import AuditLog

MAX_TEAM_MEMBERS = 50


class TeamWorkspaceService:
    def __init__(
        self,
        teams: TeamRepository,
        users: SeedUserRepository,
        audit_log: AuditLog,
    ) -> None:
        self._teams = teams
        self._users = users
        self._audit_log = audit_log

    def list_teams(self, actor: UserAccount) -> tuple[OrgTeam, ...]:
        return tuple(team for team in self._teams.list_teams() if self._can_view(actor, team))

    def team_details(self, actor: UserAccount, team_id: UUID) -> OrgTeam:
        team = self._teams.get_team(team_id)
        if team is None or not self._can_view(actor, team):
            raise AppError(404, "team_not_found", "Team was not found.")
        return team

    def roster(self, actor: UserAccount, team_id: UUID) -> tuple[UserAccount, ...]:
        team = self.team_details(actor, team_id)
        member_ids = sorted(team_member_ids(team), key=str)
        members = (self._users.get_by_id(user_id) for user_id in member_ids)
        return tuple(member for member in members if member is not None)

    def member_candidates(
        self, actor: UserAccount, team_id: UUID, query: str
    ) -> tuple[UserAccount, ...]:
        team = self._managed_team(actor, team_id)
        member_ids = team_member_ids(team)
        needle = query.strip().casefold()
        if len(needle) < 3:
            return ()
        return tuple(
            user
            for user in self._users.list_users()
            if user.is_active
            and user.user_id not in member_ids
            and needle in f"{user.display_name} {user.username}".casefold()
        )[:20]

    def add_member(self, actor: UserAccount, team_id: UUID, user_id: UUID) -> OrgTeam:
        team = self._managed_team(actor, team_id)
        user = self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AppError(422, "invalid_member", "Team members must be active accounts.")
        if user_id in team_member_ids(team):
            raise AppError(409, "already_member", "The user is already on the team.")
        if len(team_member_ids(team)) >= MAX_TEAM_MEMBERS:
            raise AppError(409, "team_full", "The team has reached its member limit.")
        updated = replace(team, member_user_ids=(*team.member_user_ids, user_id))
        # Profiles are synthesised on read when absent. Avoid a second
        # persistence transaction after membership has already been audited.
        self._save_team_with_audit(actor, team, updated, "team_member_added", user_id)
        return updated

    def remove_member(self, actor: UserAccount, team_id: UUID, user_id: UUID) -> OrgTeam:
        team = self._managed_team(actor, team_id)
        if user_id not in team.member_user_ids:
            raise AppError(404, "member_not_found", "The user is not a member of the team.")
        updated = replace(
            team,
            member_user_ids=tuple(member for member in team.member_user_ids if member != user_id),
        )
        self._save_team_with_audit(actor, team, updated, "team_member_removed", user_id)
        return updated

    def get_profile(self, actor: UserAccount, user_id: UUID) -> UserProfile:
        if actor.user_id != user_id and not self._shares_team(actor, user_id):
            raise AppError(404, "profile_not_found", "Profile was not found.")
        profile = self._teams.get_profile(user_id)
        if profile is None:
            user = self._users.get_by_id(user_id)
            if user is None:
                raise AppError(404, "profile_not_found", "Profile was not found.")
            profile = UserProfile(user_id=user_id, title=user.display_name)
        return profile

    def update_my_profile(
        self, actor: UserAccount, title: str, specialisms: tuple[str, ...], bio: str
    ) -> UserProfile:
        if Permission.USER_UPDATE_SELF not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        profile = UserProfile(
            user_id=actor.user_id,
            title=title.strip(),
            specialisms=tuple(dict.fromkeys(item.strip() for item in specialisms if item.strip())),
            bio=bio.strip(),
            updated_at=datetime.now(UTC),
        )
        original = self._teams.get_profile(actor.user_id)
        self._teams.save_profile(profile)
        try:
            self._audit_log.record(
                "profile_updated", str(actor.user_id), {"user_id": str(actor.user_id)}
            )
        except Exception:
            if original is None:
                self._teams.delete_profile(actor.user_id)
            else:
                self._teams.save_profile(original)
            raise
        return profile

    def _can_view(self, actor: UserAccount, team: OrgTeam) -> bool:
        if Permission.ROLE_MANAGE in actor.permissions:
            return True
        return actor.user_id in team_member_ids(team)

    def _managed_team(self, actor: UserAccount, team_id: UUID) -> OrgTeam:
        if Permission.TEAM_MANAGE not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        team = self._teams.get_team(team_id)
        if team is None or not self._can_view(actor, team):
            raise AppError(404, "team_not_found", "Team was not found.")
        is_admin = Permission.ROLE_MANAGE in actor.permissions
        if not is_admin and actor.user_id not in team.manager_user_ids:
            raise AppError(403, "forbidden", "Only the team's managers can change its roster.")
        return team

    def _shares_team(self, actor: UserAccount, user_id: UUID) -> bool:
        if Permission.ROLE_MANAGE in actor.permissions:
            return True
        return any(
            actor.user_id in team_member_ids(team) and user_id in team_member_ids(team)
            for team in self._teams.list_teams()
        )

    def _save_team_with_audit(
        self,
        actor: UserAccount,
        original: OrgTeam,
        updated: OrgTeam,
        event_type: str,
        user_id: UUID,
    ) -> None:
        self._teams.save_team(updated)
        try:
            self._audit_log.record(
                event_type,
                str(actor.user_id),
                {"team_id": str(updated.team_id), "user_id": str(user_id)},
            )
        except Exception:
            self._teams.save_team(original)
            raise

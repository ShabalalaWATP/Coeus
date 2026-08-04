"""Machine-readable integrity evidence for the compatibility workforce seed."""

from dataclasses import dataclass

from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.teams import OrgTeam, TeamKind, team_member_ids


@dataclass(frozen=True)
class SyntheticWorkforceIntegrityReport:
    persona_count: int
    analyst_count: int
    rfa_analyst_count: int
    cm_analyst_count: int
    cross_posted_analyst_count: int
    duplicate_username_count: int
    duplicate_display_name_count: int
    delivery_leaf_shortfalls: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def inspect_synthetic_workforce(
    users: tuple[UserAccount, ...], teams: tuple[OrgTeam, ...]
) -> SyntheticWorkforceIntegrityReport:
    analysts = {
        user.user_id: user
        for user in users
        if user.roles == frozenset({RoleName.INTELLIGENCE_ANALYST})
    }
    delivery = tuple(team for team in teams if team.kind in {TeamKind.RFA, TeamKind.CM})
    routes_by_analyst = {
        user_id: tuple(team.kind for team in delivery if user_id in set(team_member_ids(team)))
        for user_id in analysts
    }
    rfa = sum(kinds == (TeamKind.RFA,) for kinds in routes_by_analyst.values())
    cm = sum(kinds == (TeamKind.CM,) for kinds in routes_by_analyst.values())
    cross_posted = sum(len(kinds) > 1 for kinds in routes_by_analyst.values())
    shortfalls = tuple(
        sorted(
            team.name
            for team in delivery
            if sum(
                user_id in analysts and analysts[user_id].is_active
                for user_id in team_member_ids(team)
            )
            < 3
        )
    )
    duplicate_usernames = len(users) - len({user.username.casefold() for user in users})
    duplicate_names = len(users) - len({user.display_name.casefold() for user in users})
    errors: list[str] = []
    _expect(errors, len(users) == 53, "persona_count")
    _expect(errors, len(analysts) == 24, "analyst_count")
    _expect(errors, rfa == 14, "rfa_analyst_count")
    _expect(errors, cm == 10, "cm_analyst_count")
    _expect(errors, cross_posted == 0, "cross_posted_analysts")
    _expect(errors, duplicate_usernames == 0, "duplicate_usernames")
    _expect(errors, duplicate_names == 0, "duplicate_display_names")
    _expect(errors, not shortfalls, "delivery_leaf_shortfalls")
    return SyntheticWorkforceIntegrityReport(
        len(users),
        len(analysts),
        rfa,
        cm,
        cross_posted,
        duplicate_usernames,
        duplicate_names,
        shortfalls,
        tuple(errors),
    )


def _expect(errors: list[str], condition: bool, code: str) -> None:
    if not condition:
        errors.append(code)

from typing import Protocol

from coeus.domain.capabilities import CandidateTeam, CapabilityDepartment, CapabilityTeam
from coeus.services.capability_catalogue_data import CM_TEAM_SPECS, RFA_TEAM_SPECS
from coeus.services.capability_recommendation import recommend_teams

TeamSpec = tuple[str, str, str, str, str, float]


class CapabilityCataloguePort(Protocol):
    """Read/recommendation boundary consumed by routing services and agents."""

    def recommend_rfa(
        self,
        terms: frozenset[str],
        *,
        disciplines: frozenset[str] = frozenset(),
        region: str | None = None,
        priority_tier: str | None = None,
    ) -> tuple[CandidateTeam, ...]: ...

    def recommend_cm(
        self,
        terms: frozenset[str],
        *,
        disciplines: frozenset[str] = frozenset(),
        region: str | None = None,
        priority_tier: str | None = None,
    ) -> tuple[CandidateTeam, ...]: ...

    def team(self, team_id: str) -> CapabilityTeam | None: ...

    def default_cm_team(self) -> CapabilityTeam: ...

    def rfa_teams(self) -> tuple[CapabilityTeam, ...]: ...

    def cm_teams(self) -> tuple[CapabilityTeam, ...]: ...


class CapabilityCatalogue:
    def __init__(self) -> None:
        self._rfa_teams = tuple(_rfa_team(*spec) for spec in RFA_TEAM_SPECS)
        self._cm_teams = tuple(_cm_team(*spec) for spec in CM_TEAM_SPECS)
        self._by_id = {team.team_id: team for team in (*self._rfa_teams, *self._cm_teams)}

    def recommend_rfa(
        self,
        terms: frozenset[str],
        *,
        disciplines: frozenset[str] = frozenset(),
        region: str | None = None,
        priority_tier: str | None = None,
    ) -> tuple[CandidateTeam, ...]:
        return recommend_teams(
            self._rfa_teams,
            terms=terms,
            disciplines=disciplines,
            region=region,
            priority_tier=priority_tier,
        )

    def recommend_cm(
        self,
        terms: frozenset[str],
        *,
        disciplines: frozenset[str] = frozenset(),
        region: str | None = None,
        priority_tier: str | None = None,
    ) -> tuple[CandidateTeam, ...]:
        return recommend_teams(
            self._cm_teams,
            terms=terms,
            disciplines=disciplines,
            region=region,
            priority_tier=priority_tier,
        )

    def team(self, team_id: str) -> CapabilityTeam | None:
        return self._by_id.get(team_id)

    def best_rfa_team(self, terms: frozenset[str]) -> CapabilityTeam:
        candidates = self.recommend_rfa(terms)
        if candidates:
            team = self.team(candidates[0].team_id)
            if team is not None:
                return team
        # No signal at all: the triage cell owns unmatched assessments.
        return self._rfa_teams[-1]

    def best_cm_team(self, terms: frozenset[str]) -> CapabilityTeam | None:
        candidates = self.recommend_cm(terms)
        if not candidates:
            return None
        return self.team(candidates[0].team_id)

    def default_cm_team(self) -> CapabilityTeam:
        return self._cm_teams[-1]

    def rfa_teams(self) -> tuple[CapabilityTeam, ...]:
        return self._rfa_teams

    def cm_teams(self) -> tuple[CapabilityTeam, ...]:
        return self._cm_teams


def _rfa_team(
    team_id: str, name: str, keywords: str, disciplines: str, regions: str, rank: float
) -> CapabilityTeam:
    return CapabilityTeam(
        team_id=team_id,
        name=name,
        department=CapabilityDepartment.RFA,
        keywords=frozenset(keywords.split()),
        work_packages=(
            f"Validate the requirement with {name}.",
            "Identify evidence gaps and assumptions.",
            "Prepare analyst handover notes.",
        ),
        disciplines=_tags(disciplines),
        regions=_regions(regions),
        rank=rank,
    )


def _cm_team(
    team_id: str, name: str, keywords: str, disciplines: str, regions: str, rank: float
) -> CapabilityTeam:
    source = name.replace(" Cell", "").replace("Collection ", "").casefold()
    return CapabilityTeam(
        team_id=team_id,
        name=name,
        department=CapabilityDepartment.CM,
        keywords=frozenset(keywords.split()),
        work_packages=(
            f"Confirm collection feasibility with {name}.",
            "Define tasking constraints and source access.",
        ),
        source_labels=(source, "collection manager coordination"),
        disciplines=_tags(disciplines),
        regions=_regions(regions),
        rank=rank,
    )


def _tags(value: str) -> frozenset[str]:
    return frozenset(tag for tag in value.split() if tag)


def _regions(value: str) -> frozenset[str]:
    return frozenset(region.strip() for region in value.split(",") if region.strip())

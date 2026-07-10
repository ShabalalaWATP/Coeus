from typing import cast
from uuid import uuid4

from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.capabilities import CapabilityDepartment, CapabilityTeam
from coeus.services.audit import AuditLog
from coeus.services.routing import RoutingService
from coeus.services.routing_agents import CmReviewAgent, RfaReviewAgent
from coeus.services.tickets import TicketServices


class FakeCatalogue:
    def __init__(self) -> None:
        self.rfa = _team("fake-rfa", CapabilityDepartment.RFA)
        self.cm = _team("fake-cm", CapabilityDepartment.CM)

    def recommend_rfa(self, terms: frozenset[str], **_kwargs: object) -> tuple[()]:
        return ()

    def recommend_cm(self, terms: frozenset[str], **_kwargs: object) -> tuple[()]:
        return ()

    def team(self, team_id: str) -> CapabilityTeam | None:
        return {self.rfa.team_id: self.rfa, self.cm.team_id: self.cm}.get(team_id)

    def default_cm_team(self) -> CapabilityTeam:
        return self.cm

    def rfa_teams(self) -> tuple[CapabilityTeam, ...]:
        return (self.rfa,)

    def cm_teams(self) -> tuple[CapabilityTeam, ...]:
        return (self.cm,)


class IndependentRfaAgent:
    def review(self, _ticket: object) -> None:
        raise AssertionError("Catalogue reads must not invoke the RFA agent.")


class IndependentCmAgent:
    def review(self, _ticket: object) -> None:
        raise AssertionError("Catalogue reads must not invoke the CM agent.")


def test_routing_service_uses_injected_catalogue_and_independent_agents() -> None:
    catalogue = FakeCatalogue()
    rfa_agent = IndependentRfaAgent()
    cm_agent = IndependentCmAgent()
    service = RoutingService(
        cast(TicketServices, object()),
        AuditLog(),
        catalogue,
        cast(RfaReviewAgent, rfa_agent),
        cast(CmReviewAgent, cm_agent),
    )
    actor = UserAccount(
        user_id=uuid4(),
        username="manager@example.test",
        display_name="Manager",
        roles=frozenset({RoleName.RFA_MANAGER}),
        permissions=frozenset({Permission.RFA_REVIEW}),
        password_hash="unused",  # noqa: S106 - domain fixture, never authenticated
        is_active=True,
        clearance_level=3,
    )

    teams = service.capability_catalogue(actor)

    assert teams == (catalogue.rfa, catalogue.cm)


def _team(team_id: str, department: CapabilityDepartment) -> CapabilityTeam:
    return CapabilityTeam(
        team_id=team_id,
        name=team_id,
        department=department,
        keywords=frozenset(),
        work_packages=(),
    )

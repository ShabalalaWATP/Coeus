"""Explicit exercise-only hierarchy and single-home workforce manifest."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.domain.organisation import (
    DeliveryRoute,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
)

BASELINE = datetime(2026, 8, 3, tzinfo=UTC)


@dataclass(frozen=True)
class SyntheticUnitSpec:
    key: str
    name: str
    short_name: str
    category: OrganisationCategory
    parent_key: str | None
    route: DeliveryRoute | None = None
    wip_limit: int | None = None

    @property
    def unit_id(self) -> UUID:
        return synthetic_unit_id(self.key)


def synthetic_unit_id(key: str) -> UUID:
    """Return the stable canonical identity for an exercise organisation unit."""
    return uuid5(NAMESPACE_URL, f"coeus:synthetic-unit:v2:{key}")


@dataclass(frozen=True)
class SyntheticPostingSpec:
    username: str
    unit_key: str
    role: MembershipRole
    state: MembershipState = MembershipState.ACTIVE
    assignment_eligible: bool = False
    valid_from: datetime = BASELINE
    valid_until: datetime | None = None
    record_key: str | None = None

    @property
    def membership_id(self) -> UUID:
        key = self.record_key or self.username
        return uuid5(NAMESPACE_URL, f"coeus:synthetic-posting:v2:{key}")


@dataclass(frozen=True)
class SyntheticWorkingPatternSpec:
    username: str
    unit_key: str
    weekday_minutes: int
    valid_from: datetime = BASELINE

    @property
    def pattern_id(self) -> UUID:
        return uuid5(NAMESPACE_URL, f"coeus:synthetic-pattern:v2:{self.username}")


def synthetic_unit_specs() -> tuple[SyntheticUnitSpec, ...]:
    command = OrganisationCategory.COMMAND
    branch = OrganisationCategory.BRANCH
    delivery = OrganisationCategory.DELIVERY_TEAM
    governance = OrganisationCategory.GOVERNANCE_TEAM
    customer = OrganisationCategory.CUSTOMER_TEAM
    return (
        SyntheticUnitSpec("di", "Defence Intelligence", "DI", command, None),
        SyntheticUnitSpec("joint", "DI Joint User", "DI JU", branch, "di"),
        SyntheticUnitSpec("ncgia", "DI NCGIA", "NCGIA", customer, "joint"),
        SyntheticUnitSpec("mis", "MIS", "MIS", customer, "joint"),
        SyntheticUnitSpec("uksf", "UKSF", "UKSF", branch, "di"),
        SyntheticUnitSpec("sas", "SAS", "SAS", customer, "uksf"),
        SyntheticUnitSpec("sbs", "SBS", "SBS", customer, "uksf"),
        SyntheticUnitSpec("srr", "SRR", "SRR", customer, "uksf"),
        SyntheticUnitSpec("18sr", "18SR", "18SR", customer, "uksf"),
        SyntheticUnitSpec("pagc", "PAGC", "PAGC", branch, "di"),
        SyntheticUnitSpec("14sr", "14SR", "14SR", customer, "pagc"),
        SyntheticUnitSpec("4rangers", "4 RANGERS", "4 RGR", customer, "pagc"),
        SyntheticUnitSpec("platform", "Platform Governance", "PLAT", governance, "di"),
        SyntheticUnitSpec("jioc", "JIOC Routing Cell", "JIOC", governance, "joint"),
        SyntheticUnitSpec("qc", "Quality Control Cell", "QC", governance, "joint"),
        SyntheticUnitSpec("store", "Intelligence Store Governance", "STORE", governance, "joint"),
        SyntheticUnitSpec("rfa", "RFA Delivery", "RFA", branch, "joint"),
        SyntheticUnitSpec(
            "rfa_maritime", "RFA Assessment Team", "RFA MAR", delivery, "rfa", DeliveryRoute.RFA, 8
        ),
        SyntheticUnitSpec(
            "rfa_land",
            "All-source and Land Assessment",
            "RFA LAND",
            delivery,
            "rfa",
            DeliveryRoute.RFA,
            8,
        ),
        SyntheticUnitSpec(
            "rfa_cyber",
            "Cyber and Technical Assessment",
            "RFA CYB",
            delivery,
            "rfa",
            DeliveryRoute.RFA,
            8,
        ),
        SyntheticUnitSpec(
            "rfa_regional",
            "Regional and Open-source Assessment",
            "RFA REG",
            delivery,
            "rfa",
            DeliveryRoute.RFA,
            8,
        ),
        SyntheticUnitSpec("cm", "Collection Management Delivery", "CM", branch, "joint"),
        SyntheticUnitSpec(
            "cm_open", "Collection Management Team", "CM OSINT", delivery, "cm", DeliveryRoute.CM, 8
        ),
        SyntheticUnitSpec(
            "cm_geo", "Geospatial Collection", "CM GEO", delivery, "cm", DeliveryRoute.CM, 8
        ),
        SyntheticUnitSpec(
            "cm_requirements",
            "Collection Requirements and Coordination",
            "CM REQ",
            delivery,
            "cm",
            DeliveryRoute.CM,
            8,
        ),
    )


def synthetic_posting_specs() -> tuple[SyntheticPostingSpec, ...]:
    rows = [
        _posting("admin@example.test", "platform", MembershipRole.MANAGER),
        _posting("admin.2@example.test", "platform", MembershipRole.MEMBER),
        _posting("user@example.test", "ncgia"),
        _posting("colleague@example.test", "mis"),
        _posting("customer.3@example.test", "sas"),
        _posting("customer.4@example.test", "sbs"),
        _posting("customer.5@example.test", "14sr"),
        _posting("customer.6@example.test", "4rangers"),
        _posting(
            "disabled@example.test",
            "srr",
            state=MembershipState.ENDED,
            valid_from=BASELINE - timedelta(days=365),
            valid_until=BASELINE,
        ),
        _posting("jioc.team@example.test", "jioc", MembershipRole.MANAGER),
        _posting("jioc.member@example.test", "jioc"),
        _posting("jioc.3@example.test", "jioc"),
        _posting("rfa.manager@example.test", "rfa", MembershipRole.MANAGER),
        _posting("rfa.team@example.test", "rfa_maritime", MembershipRole.MANAGER),
        _posting("rfa.lead.2@example.test", "rfa_land", MembershipRole.MANAGER),
        _posting("rfa.lead.3@example.test", "rfa_cyber", MembershipRole.MANAGER),
        _posting("rfa.lead.4@example.test", "rfa_regional", MembershipRole.MANAGER),
        _posting("rfa.coordinator@example.test", "rfa", MembershipRole.COORDINATOR),
        _posting("collection.manager@example.test", "cm", MembershipRole.MANAGER),
        _posting("collection.team@example.test", "cm_open", MembershipRole.MANAGER),
        _posting("cm.lead.2@example.test", "cm_geo", MembershipRole.MANAGER),
        _posting("cm.lead.3@example.test", "cm_requirements", MembershipRole.MANAGER),
        _posting("cm.deputy@example.test", "cm", MembershipRole.DEPUTY),
        _posting("cm.coordinator@example.test", "cm", MembershipRole.COORDINATOR),
        _posting("qc.manager@example.test", "qc", MembershipRole.MANAGER),
        _posting("qc.reviewer.2@example.test", "qc"),
        _posting("qc.reviewer.3@example.test", "qc"),
        _posting("store.manager@example.test", "store", MembershipRole.MANAGER),
        _posting("store.curator@example.test", "store"),
    ]
    rows.extend(_analyst_postings())
    rows.append(
        _posting(
            "analyst.13@example.test",
            "rfa_land",
            state=MembershipState.ENDED,
            valid_from=BASELINE - timedelta(days=180),
            valid_until=BASELINE - timedelta(days=30),
            record_key="analyst.13@example.test:prior-rfa-land",
        )
    )
    return tuple(rows)


def synthetic_working_patterns() -> tuple[SyntheticWorkingPatternSpec, ...]:
    return tuple(
        SyntheticWorkingPatternSpec(
            posting.username,
            posting.unit_key,
            360 if posting.username == "analyst.20@example.test" else 480,
            posting.valid_from,
        )
        for posting in synthetic_posting_specs()
        if posting.assignment_eligible
        or posting.username
        in {
            "analyst.14@example.test",
            "analyst.15@example.test",
            "analyst.24@example.test",
        }
    )


def _analyst_postings() -> list[SyntheticPostingSpec]:
    allocations = {
        "rfa_maritime": (
            "analyst@example.test",
            "analyst.2@example.test",
            "analyst.4@example.test",
        ),
        "rfa_land": tuple(f"analyst.{index}@example.test" for index in (5, 6, 7, 15)),
        "rfa_cyber": tuple(f"analyst.{index}@example.test" for index in (8, 9, 10, 14)),
        "rfa_regional": tuple(f"analyst.{index}@example.test" for index in (11, 12, 13)),
        "cm_open": ("analyst.3@example.test", "analyst.16@example.test", "analyst.17@example.test"),
        "cm_geo": tuple(f"analyst.{index}@example.test" for index in (18, 19, 20, 24)),
        "cm_requirements": tuple(f"analyst.{index}@example.test" for index in (21, 22, 23)),
    }
    rows: list[SyntheticPostingSpec] = []
    for unit_key, usernames in allocations.items():
        for username in usernames:
            state = MembershipState.ACTIVE
            eligible = True
            valid_from = BASELINE
            valid_until = None
            if username == "analyst.14@example.test":
                state, eligible = MembershipState.ENDED, False
                valid_from, valid_until = BASELINE - timedelta(days=365), BASELINE
            elif username == "analyst.15@example.test":
                eligible, valid_from = False, BASELINE + timedelta(days=28)
            elif username == "analyst.24@example.test":
                state, eligible = MembershipState.SUSPENDED, False
            rows.append(
                _posting(
                    username,
                    unit_key,
                    state=state,
                    eligible=eligible,
                    valid_from=valid_from,
                    valid_until=valid_until,
                )
            )
    return rows


def _posting(
    username: str,
    unit_key: str,
    role: MembershipRole = MembershipRole.MEMBER,
    *,
    state: MembershipState = MembershipState.ACTIVE,
    eligible: bool = False,
    valid_from: datetime = BASELINE,
    valid_until: datetime | None = None,
    record_key: str | None = None,
) -> SyntheticPostingSpec:
    return SyntheticPostingSpec(
        username, unit_key, role, state, eligible, valid_from, valid_until, record_key
    )

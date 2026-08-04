"""One-shot organisation bootstrap command and result records."""

from dataclasses import dataclass
from uuid import UUID

from coeus.domain.organisation import OrganisationCategory
from coeus.domain.organisation_validation import optional_text, text_value


class OrganisationBootstrapDenied(PermissionError):
    pass


class OrganisationBootstrapUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class BootstrapOrganisationCommand:
    command_id: UUID
    actor_user_id: UUID
    root_unit_id: UUID
    root_name: str
    root_short_name: str
    time_zone: str
    setup_nonce: str
    description: str = ""

    def __post_init__(self) -> None:
        text_value(self.root_name, "root_name", 120)
        text_value(self.root_short_name, "root_short_name", 32)
        text_value(self.time_zone, "time_zone", 64)
        optional_text(self.description, "description", 1_000)
        if not 32 <= len(self.setup_nonce) <= 256:
            raise ValueError("setup_nonce must contain 32 to 256 characters")
        if self.setup_nonce != self.setup_nonce.strip():
            raise ValueError("setup_nonce must not contain surrounding whitespace")


@dataclass(frozen=True)
class OrganisationBootstrapPlan:
    command_id: UUID
    actor_user_id: UUID
    root_unit_id: UUID
    root_name: str
    root_short_name: str
    time_zone: str
    description: str
    category: OrganisationCategory = OrganisationCategory.COMMAND


@dataclass(frozen=True)
class OrganisationBootstrapResult:
    root_unit_id: UUID
    topology_revision_id: UUID
    grant_ids: tuple[UUID, ...]

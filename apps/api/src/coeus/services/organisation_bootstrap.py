"""Policy boundary for the one-shot organisation bootstrap ceremony."""

from hmac import compare_digest

from coeus.application.ports.organisation_bootstrap import OrganisationBootstrapStore
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.organisation_bootstrap import (
    BootstrapOrganisationCommand,
    OrganisationBootstrapDenied,
    OrganisationBootstrapPlan,
    OrganisationBootstrapResult,
)


class OrganisationBootstrapService:
    def __init__(self, store: OrganisationBootstrapStore, expected_nonce: str | None) -> None:
        self._store = store
        self._expected_nonce = expected_nonce

    def execute(
        self,
        command: BootstrapOrganisationCommand,
        actor: UserAccount,
        *,
        reauthenticated: bool,
    ) -> OrganisationBootstrapResult:
        if command.actor_user_id != actor.user_id:
            raise OrganisationBootstrapDenied("bootstrap actor identity does not match")
        if (
            not actor.is_active
            or RoleName.ADMINISTRATOR not in actor.roles
            or Permission.SYSTEM_CONFIGURE not in actor.permissions
        ):
            raise OrganisationBootstrapDenied("platform administrator authority is required")
        if not reauthenticated:
            raise OrganisationBootstrapDenied("recent reauthentication is required")
        if self._expected_nonce is None or not compare_digest(
            command.setup_nonce.encode(), self._expected_nonce.encode()
        ):
            raise OrganisationBootstrapDenied("the setup nonce is invalid")
        return self._store.bootstrap(
            OrganisationBootstrapPlan(
                command.command_id,
                command.actor_user_id,
                command.root_unit_id,
                command.root_name,
                command.root_short_name,
                command.time_zone,
                command.description,
            )
        )

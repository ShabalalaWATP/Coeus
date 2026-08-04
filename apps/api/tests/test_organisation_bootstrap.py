from dataclasses import replace
from uuid import uuid4

import pytest

from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.organisation_bootstrap import (
    BootstrapOrganisationCommand,
    OrganisationBootstrapDenied,
    OrganisationBootstrapResult,
)
from coeus.services.organisation_bootstrap import OrganisationBootstrapService

NONCE = "synthetic-bootstrap-nonce-value-123456"


class _Store:
    def __init__(self) -> None:
        self.plan = None

    def bootstrap(self, plan):  # type: ignore[no-untyped-def]
        self.plan = plan
        return OrganisationBootstrapResult(plan.root_unit_id, uuid4(), ())


def _actor(
    *, active: bool = True, administrator: bool = True, configure: bool = True
) -> UserAccount:
    return UserAccount(
        uuid4(),
        "bootstrap.admin@example.test",
        "Bootstrap Administrator",
        frozenset({RoleName.ADMINISTRATOR} if administrator else {RoleName.USER}),
        frozenset({Permission.SYSTEM_CONFIGURE} if configure else ()),
        "not-a-real-hash",
        active,
        3,
    )


def _command(actor: UserAccount) -> BootstrapOrganisationCommand:
    return BootstrapOrganisationCommand(
        uuid4(),
        actor.user_id,
        uuid4(),
        "Synthetic Defence Intelligence",
        "Synthetic DI",
        "Europe/London",
        NONCE,
        "Synthetic root organisation used for local exercises.",
    )


def test_bootstrap_requires_matching_reauthenticated_platform_administrator() -> None:
    actor = _actor()
    command = _command(actor)
    service = OrganisationBootstrapService(_Store(), NONCE)
    with pytest.raises(OrganisationBootstrapDenied, match="identity"):
        service.execute(replace(command, actor_user_id=uuid4()), actor, reauthenticated=True)
    for denied_actor in (
        _actor(active=False),
        _actor(administrator=False),
        _actor(configure=False),
    ):
        denied_command = replace(command, actor_user_id=denied_actor.user_id)
        with pytest.raises(OrganisationBootstrapDenied, match="administrator authority"):
            service.execute(denied_command, denied_actor, reauthenticated=True)
    with pytest.raises(OrganisationBootstrapDenied, match="reauthentication"):
        service.execute(command, actor, reauthenticated=False)


def test_bootstrap_nonce_is_required_and_never_passed_to_persistence() -> None:
    actor = _actor()
    command = _command(actor)
    store = _Store()
    with pytest.raises(OrganisationBootstrapDenied, match="nonce"):
        OrganisationBootstrapService(store, None).execute(command, actor, reauthenticated=True)
    with pytest.raises(OrganisationBootstrapDenied, match="nonce"):
        OrganisationBootstrapService(store, "x" * 32).execute(command, actor, reauthenticated=True)
    result = OrganisationBootstrapService(store, NONCE).execute(
        command, actor, reauthenticated=True
    )
    assert result.root_unit_id == command.root_unit_id
    assert store.plan is not None
    assert "nonce" not in vars(store.plan)


@pytest.mark.parametrize(
    "change",
    (
        {"setup_nonce": "short"},
        {"setup_nonce": f"{'x' * 32} "},
        {"root_name": ""},
        {"root_short_name": ""},
        {"time_zone": ""},
        {"description": "x" * 1_001},
    ),
)
def test_bootstrap_command_rejects_unbounded_fields(change: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(_command(_actor()), **change)

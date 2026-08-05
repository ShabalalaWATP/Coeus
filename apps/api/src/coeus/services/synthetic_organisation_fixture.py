"""Policy boundary for the local-only synthetic organisation fixture."""

from coeus.application.ports.synthetic_organisation_fixture import (
    SyntheticOrganisationFixtureStore,
)
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureCommand,
    SyntheticFixturePreview,
    SyntheticFixtureResult,
    SyntheticFixtureUnavailable,
    SyntheticFixtureUser,
)
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.synthetic_organisation_manifest import synthetic_posting_specs


class SyntheticOrganisationFixtureService:
    def __init__(
        self,
        store: SyntheticOrganisationFixtureStore,
        users: SeedUserRepository,
        *,
        enabled: bool,
    ) -> None:
        self._store = store
        self._users = users
        self._enabled = enabled

    def preview(self, actor: UserAccount) -> SyntheticFixturePreview:
        self._require_actor(actor)
        return self._store.preview(actor.user_id, self._fixture_users())

    def apply(
        self,
        command: SyntheticFixtureCommand,
        actor: UserAccount,
        *,
        reauthenticated: bool,
    ) -> SyntheticFixtureResult:
        self._require_actor(actor)
        if command.actor_user_id != actor.user_id or not reauthenticated:
            raise SyntheticFixtureUnavailable("fresh administrator authentication is required")
        users = self._fixture_users()
        result: SyntheticFixtureResult | None = None

        def commit() -> None:
            nonlocal result
            result = self._store.apply(command, users)

        current = self._users.confirm_current_authority(
            actor,
            frozenset({Permission.SYSTEM_CONFIGURE}),
            commit,
        )
        if not current or result is None:
            raise SyntheticFixtureUnavailable("administrator authority changed before apply")
        return result

    def reconcile(
        self,
        command: SyntheticFixtureCommand,
        actor: UserAccount,
        *,
        reauthenticated: bool,
    ) -> SyntheticFixtureResult:
        return self._execute(command, actor, reauthenticated, reconcile=True)

    def _execute(
        self,
        command: SyntheticFixtureCommand,
        actor: UserAccount,
        reauthenticated: bool,
        *,
        reconcile: bool,
    ) -> SyntheticFixtureResult:
        self._require_actor(actor)
        if command.actor_user_id != actor.user_id or not reauthenticated:
            raise SyntheticFixtureUnavailable("fresh administrator authentication is required")
        users = self._fixture_users()
        result: SyntheticFixtureResult | None = None

        def commit() -> None:
            nonlocal result
            operation = self._store.reconcile if reconcile else self._store.apply
            result = operation(command, users)

        current = self._users.confirm_current_authority(
            actor, frozenset({Permission.SYSTEM_CONFIGURE}), commit
        )
        if not current or result is None:
            raise SyntheticFixtureUnavailable("administrator authority changed before apply")
        return result

    def _require_actor(self, actor: UserAccount) -> None:
        if not self._enabled:
            raise SyntheticFixtureUnavailable("synthetic organisation fixtures are disabled")
        if not actor.is_active or Permission.SYSTEM_CONFIGURE not in actor.permissions:
            raise SyntheticFixtureUnavailable("platform administrator authority is required")

    def _fixture_users(self) -> tuple[SyntheticFixtureUser, ...]:
        resolved: list[SyntheticFixtureUser] = []
        for username in dict.fromkeys(item.username for item in synthetic_posting_specs()):
            user = self._users.get_seed_by_canonical_username(username)
            if user is not None:
                resolved.append(SyntheticFixtureUser(username, user.user_id, user.is_active))
        return tuple(resolved)

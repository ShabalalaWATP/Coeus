from collections.abc import Callable
from typing import Protocol
from uuid import UUID, uuid5

from coeus.core.permissions import Permission
from coeus.domain.access import (
    AccessControlGroup,
    AccessControlGroupMembership,
    ProductRecord,
    ProductStatus,
)
from coeus.domain.auth import UserAccount
from coeus.persistence.state_store import StateStore
from coeus.repositories.access_seed_product import build_seed_product
from coeus.repositories.access_state import load_access_snapshot, save_access_snapshot
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.demo_access_specs import (
    BILLY_DENIED_ACG_CODES,
    THEMED_ACG_DISCIPLINES,
    THEMED_ACG_REGIONS,
    merge_demo_access,
    specialist_acgs,
)

SEED_NAMESPACE = UUID("f71d6c95-85da-4f8b-8d55-e547c227c3a4")

DEMO_ACCESS_SEED_VERSION = 2


def stable_seed_id(name: str) -> UUID:
    return uuid5(SEED_NAMESPACE, name)


class AccessRepository(Protocol):
    def list_users(self) -> tuple[UserAccount, ...]: ...

    def get_user(self, user_id: UUID) -> UserAccount | None: ...

    def get_user_by_username(self, username: str) -> UserAccount | None: ...

    def confirm_current_authority(
        self,
        expected_actor: UserAccount,
        required_permissions: frozenset[Permission],
        confirm: Callable[[], object],
    ) -> bool: ...

    def list_acgs(self) -> tuple[AccessControlGroup, ...]: ...

    def get_acg(self, acg_id: UUID) -> AccessControlGroup | None: ...

    def save_acg(self, acg: AccessControlGroup) -> None: ...

    def delete_acg(self, acg_id: UUID) -> None: ...

    def add_membership(self, acg_id: UUID, user_id: UUID) -> None: ...

    def remove_membership(self, acg_id: UUID, user_id: UUID) -> None: ...

    def list_memberships_for_acg(
        self, acg_id: UUID
    ) -> tuple[AccessControlGroupMembership, ...]: ...

    def acg_ids_for_user(self, user_id: UUID) -> frozenset[UUID]: ...

    def active_acg_ids_for_user(self, user_id: UUID) -> frozenset[UUID]: ...

    def list_products(self) -> tuple[ProductRecord, ...]: ...

    def get_product(self, product_id: UUID) -> ProductRecord | None: ...


class SeedAccessRepository:
    def __init__(
        self,
        users: SeedUserRepository,
        state_store: StateStore | None = None,
    ) -> None:
        self._users = users
        self._state_store = state_store
        self._initialising = True
        self._acgs: dict[UUID, AccessControlGroup] = {}
        self._memberships: set[AccessControlGroupMembership] = set()
        self._products: dict[UUID, ProductRecord] = {}
        self._seed_access_data()
        self._initialising = False
        self._restore_or_persist()

    def list_users(self) -> tuple[UserAccount, ...]:
        return self._users.list_users()

    def get_user(self, user_id: UUID) -> UserAccount | None:
        return self._users.get_by_id(user_id)

    def get_user_by_username(self, username: str) -> UserAccount | None:
        return self._users.get_by_username(username)

    def confirm_current_authority(
        self,
        expected_actor: UserAccount,
        required_permissions: frozenset[Permission],
        confirm: Callable[[], object],
    ) -> bool:
        return self._users.confirm_current_authority(
            expected_actor,
            required_permissions,
            confirm,
        )

    def list_acgs(self) -> tuple[AccessControlGroup, ...]:
        return tuple(sorted(self._acgs.values(), key=lambda acg: acg.code))

    def get_acg(self, acg_id: UUID) -> AccessControlGroup | None:
        return self._acgs.get(acg_id)

    def save_acg(self, acg: AccessControlGroup) -> None:
        acgs = dict(self._acgs)
        self._acgs[acg.acg_id] = acg
        try:
            self._persist()
        except Exception:
            self._acgs = acgs
            raise

    def delete_acg(self, acg_id: UUID) -> None:
        acgs = dict(self._acgs)
        memberships = set(self._memberships)
        self._acgs.pop(acg_id, None)
        self._memberships = {item for item in self._memberships if item.acg_id != acg_id}
        try:
            self._persist()
        except Exception:
            self._acgs = acgs
            self._memberships = memberships
            raise

    def add_membership(self, acg_id: UUID, user_id: UUID) -> None:
        memberships = set(self._memberships)
        self._memberships.add(AccessControlGroupMembership(acg_id=acg_id, user_id=user_id))
        try:
            self._persist()
        except Exception:
            self._memberships = memberships
            raise

    def remove_membership(self, acg_id: UUID, user_id: UUID) -> None:
        memberships = set(self._memberships)
        self._memberships.discard(AccessControlGroupMembership(acg_id=acg_id, user_id=user_id))
        try:
            self._persist()
        except Exception:
            self._memberships = memberships
            raise

    def list_memberships_for_acg(self, acg_id: UUID) -> tuple[AccessControlGroupMembership, ...]:
        return tuple(
            sorted(
                (membership for membership in self._memberships if membership.acg_id == acg_id),
                key=lambda membership: str(membership.user_id),
            )
        )

    def acg_ids_for_user(self, user_id: UUID) -> frozenset[UUID]:
        return frozenset(
            membership.acg_id for membership in self._memberships if membership.user_id == user_id
        )

    def active_acg_ids_for_user(self, user_id: UUID) -> frozenset[UUID]:
        return frozenset(
            membership.acg_id
            for membership in self._memberships
            if membership.user_id == user_id
            and (acg := self._acgs.get(membership.acg_id)) is not None
            and acg.is_active
        )

    def list_products(self) -> tuple[ProductRecord, ...]:
        return tuple(sorted(self._products.values(), key=lambda product: product.title))

    def get_product(self, product_id: UUID) -> ProductRecord | None:
        return self._products.get(product_id)

    def _restore_or_persist(self) -> None:
        if self._state_store is None:
            return
        snapshot = load_access_snapshot(self._state_store)
        if snapshot is None:
            self._persist()
            return
        self._acgs = snapshot.acgs
        self._memberships = snapshot.memberships
        self._products = snapshot.products
        marker = self._state_store.load("demo_access_seed") or {}
        if int(marker.get("version", 0)) < DEMO_ACCESS_SEED_VERSION:
            admin = self._user("admin@example.test")
            billy = self._user("colleague@example.test")
            if merge_demo_access(
                self._acgs, self._memberships, admin.user_id, billy.user_id, stable_seed_id
            ):
                self._persist()
            self._state_store.save("demo_access_seed", {"version": DEMO_ACCESS_SEED_VERSION})

    def _persist(self) -> None:
        if self._state_store is None or self._initialising:
            return
        save_access_snapshot(
            self._state_store,
            self.list_acgs(),
            self._memberships,
            self._products,
        )

    def _seed_access_data(self) -> None:
        admin = self._user("admin@example.test")
        customer = self._user("user@example.test")
        rfa_manager = self._user("rfa.manager@example.test")
        rfa_team = self._user("rfa.team@example.test")
        collection_manager = self._user("collection.manager@example.test")
        collection_team = self._user("collection.team@example.test")
        analyst = self._user("analyst@example.test")
        qc_manager = self._user("qc.manager@example.test")

        regional = self._seed_acg(
            "ACG-ALPHA-REGIONAL",
            "Alpha Regional",
            "Regional mock access group for customer-facing assessments.",
            admin.user_id,
        )
        collection = self._seed_acg(
            "ACG-BRAVO-COLLECTION",
            "Bravo Collection",
            "Collection management mock access group.",
            collection_manager.user_id,
        )
        assessment = self._seed_acg(
            "ACG-CHARLIE-ASSESSMENT",
            "Charlie Assessment",
            "Assessment cell mock access group.",
            rfa_manager.user_id,
        )

        membership_sets = (
            (regional, (admin, customer, rfa_manager)),
            (collection, (admin, collection_manager, collection_team)),
            (assessment, (admin, rfa_manager, rfa_team, analyst, qc_manager)),
        )
        for acg, members in membership_sets:
            for member in members:
                self.add_membership(acg.acg_id, member.user_id)

        themed = self._seed_themed_acgs(admin)
        colleague = self._user("colleague@example.test")
        themed_memberships: tuple[tuple[str, tuple[UserAccount, ...]], ...] = (
            ("European Cyber", (customer, colleague, rfa_manager, rfa_team, analyst, qc_manager)),
            ("European HUMINT", (rfa_manager, analyst, qc_manager)),
            ("Middle Eastern HUMINT", (rfa_manager,)),
            ("European SIGINT", (collection_manager, collection_team)),
            ("African Cyber", (collection_manager,)),
            ("Maritime GEOINT", (collection_manager,)),
        )
        for name, themed_members in themed_memberships:
            for member in themed_members:
                self.add_membership(themed[name].acg_id, member.user_id)

        for acg in specialist_acgs(admin.user_id, stable_seed_id):
            self.save_acg(acg)
            self.add_membership(acg.acg_id, admin.user_id)
        for acg in self._acgs.values():
            if acg.code not in BILLY_DENIED_ACG_CODES:
                self.add_membership(acg.acg_id, colleague.user_id)

        regional_product = build_seed_product(
            stable_seed_id("product-regional-stability-brief"),
            "Regional Stability Brief",
            "MOCK DATA ONLY assessment summary visible to Alpha Regional members.",
            "assessment_report",
            ProductStatus.PUBLISHED,
            2,
            frozenset({"MOCK"}),
            frozenset({regional.acg_id}),
            "RFA",
        )
        collection_product = build_seed_product(
            stable_seed_id("product-collection-sensor-summary"),
            "Collection Sensor Summary",
            "MOCK DATA ONLY collection product for Bravo Collection members.",
            "sigint_mock",
            ProductStatus.PUBLISHED,
            3,
            frozenset({"MOCK", "SENSOR_PLACEHOLDER"}),
            frozenset({collection.acg_id}),
            "Collection",
        )
        assessment_draft = build_seed_product(
            stable_seed_id("product-assessment-draft-pack"),
            "Assessment Draft Pack",
            "MOCK DATA ONLY draft pack for assessment team coordination.",
            "finished_output",
            ProductStatus.DRAFT,
            3,
            frozenset({"MOCK", "DRAFT"}),
            frozenset({assessment.acg_id}),
            "RFA",
        )

        self._products = {
            product.product_id: product
            for product in (regional_product, collection_product, assessment_draft)
        }

    def _seed_themed_acgs(self, admin: UserAccount) -> dict[str, AccessControlGroup]:
        themed: dict[str, AccessControlGroup] = {}
        for region_code, region in THEMED_ACG_REGIONS:
            for discipline in THEMED_ACG_DISCIPLINES:
                name = f"{region} {discipline}"
                acg = self._seed_acg(
                    f"ACG-{region_code}-{discipline.upper()}",
                    name,
                    f"Mock need-to-know group for {name} reporting.",
                    admin.user_id,
                )
                self.add_membership(acg.acg_id, admin.user_id)
                themed[name] = acg
        return themed

    def _seed_acg(
        self, code: str, name: str, description: str, owner_user_id: UUID
    ) -> AccessControlGroup:
        acg = AccessControlGroup(
            acg_id=stable_seed_id(code),
            code=code,
            name=name,
            description=description,
            owner_user_id=owner_user_id,
            is_active=True,
        )
        self.save_acg(acg)
        return acg

    def _user(self, username: str) -> UserAccount:
        user = self._users.get_by_username(username)
        if user is None:
            raise RuntimeError(f"Missing required seed user {username}.")
        return user

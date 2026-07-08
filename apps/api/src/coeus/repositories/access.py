from uuid import UUID, uuid5

from coeus.domain.access import (
    AccessControlGroup,
    AccessControlGroupMembership,
    ProductRecord,
    ProductStatus,
    ProjectMember,
    ProjectMilestone,
    ProjectPlanItem,
    ProjectWorkspace,
)
from coeus.domain.auth import UserAccount
from coeus.persistence.state_store import StateStore
from coeus.repositories.access_state import load_access_snapshot, save_access_snapshot
from coeus.repositories.auth import SeedUserRepository

SEED_NAMESPACE = UUID("f71d6c95-85da-4f8b-8d55-e547c227c3a4")

THEMED_ACG_REGIONS = (
    ("EU", "European"),
    ("AF", "African"),
    ("ME", "Middle Eastern"),
    ("AP", "Asia-Pacific"),
    ("NA", "North American"),
    ("SA", "South American"),
    ("AR", "Arctic"),
    ("MAR", "Maritime"),
)
THEMED_ACG_DISCIPLINES = ("Cyber", "HUMINT", "SIGINT", "GEOINT", "OSINT")


def stable_seed_id(name: str) -> UUID:
    return uuid5(SEED_NAMESPACE, name)


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
        self._projects: dict[UUID, ProjectWorkspace] = {}
        self._seed_access_data()
        self._initialising = False
        self._restore_or_persist()

    def list_users(self) -> tuple[UserAccount, ...]:
        return self._users.list_users()

    def get_user(self, user_id: UUID) -> UserAccount | None:
        return self._users.get_by_id(user_id)

    def get_user_by_username(self, username: str) -> UserAccount | None:
        return self._users.get_by_username(username)

    def list_acgs(self) -> tuple[AccessControlGroup, ...]:
        return tuple(sorted(self._acgs.values(), key=lambda acg: acg.code))

    def get_acg(self, acg_id: UUID) -> AccessControlGroup | None:
        return self._acgs.get(acg_id)

    def save_acg(self, acg: AccessControlGroup) -> None:
        self._acgs[acg.acg_id] = acg
        self._persist()

    def delete_acg(self, acg_id: UUID) -> None:
        self._acgs.pop(acg_id, None)
        self._memberships = {item for item in self._memberships if item.acg_id != acg_id}
        self._persist()

    def add_membership(self, acg_id: UUID, user_id: UUID) -> None:
        self._memberships.add(AccessControlGroupMembership(acg_id=acg_id, user_id=user_id))
        self._persist()

    def remove_membership(self, acg_id: UUID, user_id: UUID) -> None:
        self._memberships.discard(AccessControlGroupMembership(acg_id=acg_id, user_id=user_id))
        self._persist()

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

    def list_projects(self) -> tuple[ProjectWorkspace, ...]:
        return tuple(sorted(self._projects.values(), key=lambda project: project.reference))

    def get_project(self, project_id: UUID) -> ProjectWorkspace | None:
        return self._projects.get(project_id)

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
        self._projects = snapshot.projects

    def _persist(self) -> None:
        if self._state_store is None or self._initialising:
            return
        save_access_snapshot(
            self._state_store,
            self.list_acgs(),
            self._memberships,
            self._products,
            self._projects,
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

        regional_product = self._seed_product(
            "regional-stability-brief",
            "Regional Stability Brief",
            "MOCK DATA ONLY assessment summary visible to Alpha Regional members.",
            "assessment_report",
            ProductStatus.PUBLISHED,
            2,
            frozenset({"MOCK"}),
            frozenset({regional.acg_id}),
            "RFA",
        )
        collection_product = self._seed_product(
            "collection-sensor-summary",
            "Collection Sensor Summary",
            "MOCK DATA ONLY collection product for Bravo Collection members.",
            "sigint_mock",
            ProductStatus.PUBLISHED,
            3,
            frozenset({"MOCK", "SENSOR_PLACEHOLDER"}),
            frozenset({collection.acg_id}),
            "Collection",
        )
        assessment_draft = self._seed_product(
            "assessment-draft-pack",
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
        self._projects = {
            stable_seed_id("project-northstar"): ProjectWorkspace(
                project_id=stable_seed_id("project-northstar"),
                reference="PRJ-NORTHSTAR",
                name="Northstar RFI Workspace",
                summary=(
                    "MOCK DATA ONLY workspace linking the customer, assessment team, "
                    "ACGs and permitted products."
                ),
                requester_user_id=customer.user_id,
                acg_ids=frozenset({regional.acg_id, assessment.acg_id}),
                product_ids=frozenset(
                    {
                        regional_product.product_id,
                        collection_product.product_id,
                        assessment_draft.product_id,
                    }
                ),
                ticket_ids=frozenset({stable_seed_id("ticket-northstar")}),
                members=(
                    ProjectMember(user_id=customer.user_id, role="Requester"),
                    ProjectMember(user_id=rfa_manager.user_id, role="RFA Manager"),
                    ProjectMember(user_id=analyst.user_id, role="Analyst"),
                ),
                milestones=(
                    ProjectMilestone(
                        milestone_id=stable_seed_id("milestone-intake"),
                        title="Intake confirmed",
                        status="complete",
                    ),
                    ProjectMilestone(
                        milestone_id=stable_seed_id("milestone-review"),
                        title="Assessment review",
                        status="in_progress",
                    ),
                ),
                plan_items=(
                    ProjectPlanItem(
                        plan_item_id=stable_seed_id("plan-validate-requirement"),
                        title="Validate requirement and access groups",
                        owner_role="RFA Manager",
                        status="complete",
                    ),
                    ProjectPlanItem(
                        plan_item_id=stable_seed_id("plan-draft-product"),
                        title="Draft assessment product",
                        owner_role="Analyst",
                        status="pending",
                    ),
                ),
            )
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

    @staticmethod
    def _seed_product(
        seed_name: str,
        title: str,
        summary: str,
        product_type: str,
        status: ProductStatus,
        classification_level: int,
        handling_caveats: frozenset[str],
        acg_ids: frozenset[UUID],
        owner_team: str,
    ) -> ProductRecord:
        return ProductRecord(
            product_id=stable_seed_id(f"product-{seed_name}"),
            title=title,
            summary=summary,
            product_type=product_type,
            status=status,
            classification_level=classification_level,
            handling_caveats=handling_caveats,
            acg_ids=acg_ids,
            owner_team=owner_team,
        )

    def _user(self, username: str) -> UserAccount:
        user = self._users.get_by_username(username)
        if user is None:
            raise RuntimeError(f"Missing required seed user {username}.")
        return user

"""Load the rich local exercise dataset.

Orchestrates the deterministic demo generators: the store catalogue with its
need-to-know memberships and generated object bytes, demo tickets across the whole
workflow (which also populate the analytics dashboards), and team calendar
entries. Gated to local by ``Settings.should_seed_demo``.

Idempotency: the catalogue and memberships upsert on every boot (so an
existing local database also picks up catalogue changes) but skip cheaply once
loaded, while tickets and calendars seed only on a fresh dataset so workflow
progress and user-added entries are never reset on a persisted store.
"""

from coeus.domain.store import StoreProduct
from coeus.repositories.access import AccessRepository
from coeus.repositories.auth_seed import canonical_seed_username
from coeus.repositories.demo_calendar import build_demo_calendar
from coeus.repositories.demo_catalogue import DemoCatalogue, build_demo_catalogue
from coeus.repositories.store_seed import seed_store_products
from coeus.repositories.teams import TeamRepository
from coeus.services.demo_asset_repair import (
    materialise_demo_products,
    repair_missing_local_assets,
)
from coeus.services.demo_tickets import build_demo_tickets
from coeus.services.object_storage import ObjectStorage
from coeus.services.store import StoreServices
from coeus.services.tickets import TicketServices

# Seed users given visibility of the demo catalogue so the store, RFI search
# and analyst linking look populated for the roles a demo actually uses.
_VISIBILITY_USERS = (
    "user@example.test",
    "rfa.manager@example.test",
    "rfa.team@example.test",
    "analyst@example.test",
    "qc.manager@example.test",
    # The curator must see the catalogue they administer.
    "store.manager@example.test",
)


def seed_demo_dataset(
    access_repository: AccessRepository,
    store: StoreServices,
    object_storage: ObjectStorage,
    tickets: TicketServices,
    teams: TeamRepository,
) -> None:
    catalogue = build_demo_catalogue(access_repository)
    base_products = seed_store_products(access_repository)
    materialised_base, base_assets = materialise_demo_products(base_products)
    _seed_catalogue(
        catalogue,
        store,
        object_storage,
        base_products=materialised_base,
        base_assets=base_assets,
    )
    repair_missing_local_assets(store, object_storage)
    _grant_visibility(access_repository, catalogue.acg_codes)
    # A fresh dataset is signalled by an empty ticket store.
    if tickets.tickets.assignment_snapshot():
        return
    users = {
        canonical_seed_username(user.username): user for user in access_repository.list_users()
    }
    for ticket in build_demo_tickets(users, catalogue.products):
        tickets.tickets.save_system_update(ticket)
    for entry in build_demo_calendar(teams.list_teams()):
        teams.save_entry(entry)


def _seed_catalogue(
    catalogue: DemoCatalogue,
    store: StoreServices,
    object_storage: ObjectStorage,
    *,
    base_products: tuple[StoreProduct, ...] = (),
    base_assets: tuple[tuple[str, bytes], ...] = (),
) -> None:
    products = (*base_products, *catalogue.products)
    if not products:
        return
    # Converge both the original baseline records and the larger catalogue on
    # every local boot. The repository preserves creation timestamps and skips
    # persistence when the canonical records are already current.
    store.repository.upsert_products(products)
    for object_key, content in (*base_assets, *catalogue.generated_assets):
        if (
            not object_storage.exists(object_key)
            or object_storage.read_bytes(object_key) != content
        ):
            object_storage.write_bytes(object_key, content)


def _grant_visibility(access_repository: AccessRepository, acg_codes: frozenset[str]) -> None:
    acg_ids = {acg.code: acg.acg_id for acg in access_repository.list_acgs()}
    users = {
        canonical_seed_username(user.username): user for user in access_repository.list_users()
    }
    for username in _VISIBILITY_USERS:
        user = users.get(username)
        if user is None:
            continue
        existing = access_repository.acg_ids_for_user(user.user_id)
        for code in acg_codes:
            acg_id = acg_ids.get(code)
            if acg_id is not None and acg_id not in existing:
                access_repository.add_membership(acg_id, user.user_id)

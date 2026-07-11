"""Load the rich local demo dataset (MOCK DATA ONLY).

Orchestrates the deterministic demo generators: the store catalogue with its
need-to-know memberships and placeholder bytes, demo tickets across the whole
workflow (which also populate the analytics dashboards), and team calendar
entries. Gated to local by ``Settings.should_seed_demo``.

Idempotency: the catalogue and memberships upsert on every boot (so an
existing local database also picks up catalogue changes) but skip cheaply once
loaded, while tickets and calendars seed only on a fresh dataset so workflow
progress and user-added entries are never reset on a persisted store.
"""

from coeus.repositories.access import AccessRepository
from coeus.repositories.demo_calendar import build_demo_calendar
from coeus.repositories.demo_catalogue import DemoCatalogue, build_demo_catalogue
from coeus.repositories.demo_tickets import build_demo_tickets
from coeus.repositories.teams import TeamRepository
from coeus.services.object_storage import ObjectStorage, seed_store_asset_placeholders
from coeus.services.store import StoreServices
from coeus.services.tickets import TicketServices

# Seed users given visibility of the demo catalogue so the store, RFI search
# and analyst linking look populated for the roles a demo actually uses.
_VISIBILITY_USERS = (
    "user@example.test",
    "colleague@example.test",
    "rfa.manager@example.test",
    "rfa.team@example.test",
    "analyst@example.test",
    "qc.manager@example.test",
)


def seed_demo_dataset(
    access_repository: AccessRepository,
    store: StoreServices,
    object_storage: ObjectStorage,
    tickets: TicketServices,
    teams: TeamRepository,
) -> None:
    catalogue = build_demo_catalogue(access_repository)
    _seed_catalogue(catalogue, store, object_storage)
    _grant_visibility(access_repository, catalogue.acg_codes)
    # A fresh dataset is signalled by an empty ticket store.
    if tickets.tickets.assignment_snapshot():
        return
    users = {user.username: user for user in access_repository.list_users()}
    for ticket in build_demo_tickets(users, catalogue.products):
        tickets.tickets.save_system_update(ticket)
    for entry in build_demo_calendar(teams.list_teams()):
        teams.save_entry(entry)


def _seed_catalogue(
    catalogue: DemoCatalogue, store: StoreServices, object_storage: ObjectStorage
) -> None:
    if not catalogue.products:
        return
    # Once the last product exists the current catalogue is already loaded.
    marker = catalogue.products[-1].product_id
    if store.repository.get_product(marker) is not None:
        return
    for product in catalogue.products:
        store.repository.save_product(product)
    seed_store_asset_placeholders(object_storage, catalogue.products)


def _grant_visibility(access_repository: AccessRepository, acg_codes: frozenset[str]) -> None:
    acg_ids = {acg.code: acg.acg_id for acg in access_repository.list_acgs()}
    for username in _VISIBILITY_USERS:
        user = access_repository.get_user_by_username(username)
        if user is None:
            continue
        existing = access_repository.acg_ids_for_user(user.user_id)
        for code in acg_codes:
            acg_id = acg_ids.get(code)
            if acg_id is not None and acg_id not in existing:
                access_repository.add_membership(acg_id, user.user_id)

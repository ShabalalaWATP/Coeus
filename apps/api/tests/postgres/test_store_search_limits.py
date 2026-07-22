from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from coeus.domain.store import StoreSearchFilters, StoreVisibilityScope
from coeus.persistence.store_projection_search import search_product_page

API_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.postgres
def test_store_search_statement_deadline_is_local_to_its_transaction(
    postgres_database_url: str,
) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_database_url)
    command.upgrade(config, "head")
    engine = create_engine(postgres_database_url)
    scope = StoreVisibilityScope(
        acg_ids=frozenset({uuid4()}),
        clearance_level=5,
        include_drafts=False,
    )

    try:
        with engine.begin() as connection:
            page = search_product_page(connection, StoreSearchFilters(), scope)
            active_deadline = connection.execute(text("SHOW statement_timeout")).scalar_one()

        with engine.connect() as connection:
            reset_deadline = connection.execute(text("SHOW statement_timeout")).scalar_one()
    finally:
        engine.dispose()

    assert page.products == ()
    assert active_deadline == "1min"
    assert reset_deadline == "0"

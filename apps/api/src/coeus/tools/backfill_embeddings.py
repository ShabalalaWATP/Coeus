import sys

from coeus.core.config import Settings
from coeus.main import create_app


def main() -> None:
    """Backfill missing Store embeddings through the configured projection.

    The command is idempotent: existing embeddings are left unchanged, products
    without a PostgreSQL projection are skipped, and provider failures degrade
    to zero updates rather than blocking local startup.
    """

    app = create_app(Settings())
    updated = app.state.store_services.repository.backfill_missing_embeddings()
    sys.stdout.write(f"Backfilled {updated} product embedding(s).\n")


if __name__ == "__main__":
    main()

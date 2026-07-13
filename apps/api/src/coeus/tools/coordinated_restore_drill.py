"""Create and restore a coordinated PostgreSQL/local-object recovery bundle."""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from coeus.core.config import Settings
from coeus.services.coordinated_restore import (
    create_backup_bundle,
    restore_backup_bundle,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--target-object-root", type=Path, required=True)
    parser.add_argument("--confirm-quiesced", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_quiesced:
        parser.error("--confirm-quiesced is required")
    settings = Settings()
    if settings.persistence_provider != "postgres" or settings.object_storage_provider != "local":
        parser.error("PostgreSQL persistence and local object storage are required")
    target_database_url = os.environ.get("COEUS_RESTORE_TARGET_DATABASE_URL")
    if not target_database_url:
        parser.error("COEUS_RESTORE_TARGET_DATABASE_URL is required")
    try:
        create_backup_bundle(
            settings.database_url,
            Path(settings.local_object_storage_path),
            args.bundle,
            confirm_quiesced=True,
        )
        report = restore_backup_bundle(
            settings.database_url,
            target_database_url,
            args.bundle,
            args.target_object_root,
            confirm_quiesced=True,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        sys.stderr.write(f"Coordinated restore drill failed: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(asdict(report), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

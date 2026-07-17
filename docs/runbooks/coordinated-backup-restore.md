# Coordinated Backup And Restore Drill

This repository provides a logical recovery drill for PostgreSQL durable state
and the active local object-storage adapter. It is release evidence for Coeus
application invariants. It does not replace a production physical or managed
PostgreSQL backup test.

## Safety boundary

The source API and every worker must be stopped before backup. The target must
be a disposable, empty database and an absent or empty object directory. Never
use the live source as the restore target. The tool excludes in-flight resource
leases and clears restored outbox claims because a new process cannot inherit
ownership from the recovery point.

If administrator-entered provider credentials are in use, preserve the
configuration-encryption key separately from this bundle. For local mode this
is `COEUS_CONFIGURATION_ENCRYPTION_KEY_PATH`; hosted environments must preserve
the corresponding Secret Manager version. Never copy the key into the database
or recovery bundle. A restored database without the matching key intentionally
fails to decrypt its credential envelopes.

Set variables without placing credentials on the command line:

```powershell
$env:COEUS_PERSISTENCE_PROVIDER = "postgres"
$env:COEUS_DATABASE_URL = "postgresql+psycopg://.../source"
$env:COEUS_OBJECT_STORAGE_PROVIDER = "local"
$env:COEUS_LOCAL_OBJECT_STORAGE_PATH = "C:\recovery\source-objects"
$env:COEUS_RESTORE_TARGET_DATABASE_URL = "postgresql+psycopg://.../empty-target"
```

Run the drill:

```powershell
uv run --directory apps/api python -m coeus.tools.coordinated_restore_drill `
  --bundle "C:\recovery\bundle" `
  --target-object-root "C:\recovery\restored-objects" `
  --confirm-quiesced
```

## What the drill verifies

- The bundle contains allow-listed, explicit-column PostgreSQL binary COPY
  files for state, audit, ticket, outbox, draft-audience and Store tables.
- Every table file and object has a SHA-256 manifest entry. Unsafe paths,
  symlinks, temporary files, missing files and tampering fail closed.
- A second database export and object inventory match the first, detecting
  writers that were not actually quiesced.
- The target is migrated to the same Alembic revision and every durable table
  is empty before import.
- Resource leases are empty, outbox claims are cleared, canonical ticket rows
  validate, draft audiences have zero drift, and Store asset metadata exactly
  matches restored object key, size and SHA-256.

Preserve the JSON success report with the release-candidate revision and CI
test evidence.

## Failure and rollback

Bundle publication and object restoration use staged directories and checked
renames. PostgreSQL import is one transaction. A filesystem rename and database
commit cannot be one atomic cross-system transaction, so any failed drill
target is disposable: delete its database and object directory, fix the cause
and start again from a new empty target. Keep writers stopped until both stores
validate.

For production, also exercise the actual managed or physical database backup,
shared object-store versioning, retention, encryption, access controls and
recovery-time objective in staging. This logical drill cannot certify those
provider controls.

# Coeus Development Story, 21 July 2026

## Production-safe Store startup and workflow evidence

- Corrected Store composition so disabling demo content disables both synthetic
  product metadata and object seeding. Clean PostgreSQL and hosted starts no
  longer inherit metadata-only placeholder products that make search coverage
  appear partial.
- Updated the real PostgreSQL browser journey to prove automatic discovery,
  active JIOC RFA routing, JIOC manager on-loop oversight, bounded external PDF
  processing, RFA assignment, analyst production, human QC and customer download.
- Replaced an expiring calendar rollback fixture with relative future dates and
  allowed `AppError` traceback propagation, preventing the real application
  error from being masked by `FrozenInstanceError` in generator contexts.
- Verified the focused Store/demo backend tests (28 passed) and the complete
  ten-stage disposable PostgreSQL browser journey (10 passed).

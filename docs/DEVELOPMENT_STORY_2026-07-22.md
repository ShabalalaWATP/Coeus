# Development Story: 22 July 2026

## Security boundary remediation

- Closed all 15 reportable findings from sealed standard scan
  `59eb4efa-4acb-4504-b43c-bdab86f43cd7` without removing supported workflows.
  The remediation covers admission, Store assets and uploads, provider and
  Realtime transport, pagination, authority races, response projection, team
  calendar scope and JIOC audit authority.
- Independent review drove additional fixes for RFI visibility, provider
  watchdog hand-off, ZIP64 metadata, stale publication and manager authority,
  local lock ordering and private transport coupling.
- Split authentication sessions, Store search and seed-product construction by
  responsibility. Shared bounded HTTP now enforces JSON and Realtime deadlines.
- Resolved high-severity transitive development-tool advisories with patched
  `brace-expansion` and `js-yaml` pnpm overrides.
- PostgreSQL-backed verification passed 1,522 backend tests with one skip at
  98.14/95.05 per cent line/branch coverage. The 536-test frontend suite passed
  at 98.63/95.05 per cent, alongside the broader production gates.
- Independent reviewers found no issue in that settled diff, but follow-up scan
  `5af0222d-05d1-4c46-a090-018aff45db2d` reported three Medium and eight Low
  issues. Remediation now fences exact chat, active-work, RFI and QC sessions,
  the union of offered and grounded-evidence products, QC relationships, atomic
  active-work audit and canonical lock order. A clean-revision rescan remains
  pending under the [22 July remediation contract](specs/security-scan-remediation-2026-07-22.md).
- Expanded parser and cancellation controls pass 124 tests at 98.53 per cent
  parser-service and 95.92 per cent upload-route coverage. Authority evidence
  passes 17 administrator, 77/77 local compatibility, 99 local workflow, four
  focused and 5/5 combined real-PostgreSQL tests, including QC session
  deletion/restoration and non-offered RFI evidence races. Dependency audits
  and focused quality checks are clean.

## Product-first RFI result view

- Returned RFI results lead with the authorised product title, summary,
  classification marking and customer actions.
- Product provenance, match evidence and search diagnostics remain available in
  collapsed, keyboard-accessible disclosures at the bottom of the result.
- Added a feature spec and regression coverage for content hierarchy,
  disclosure defaults, loading, failure, degraded-search and read-only states.

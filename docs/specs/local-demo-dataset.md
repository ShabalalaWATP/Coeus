# Local Demo Dataset

## Status

Implemented (2026-07-11).

## Problem

The seed generators produced only three store products and no tickets, so a
fresh local run showed empty queues for every role and empty analytics. The
mock data needed to be rich enough to demonstrate the whole product, and it
had to travel with the repository (a `git pull` should give you the data
without any manual import).

## Approach

The mock data is committed **code**, not a database dump: deterministic
generators with stable UUIDs regenerate the dataset on an empty store, so it
is version-controlled, reviewable and reproducible, and it repopulates any
fresh database (memory, file or postgres) on first boot. This extends the
existing seed pattern rather than adding a second source of truth.

## What is generated

Gated by `Settings.should_seed_demo()` (auto-on for `environment == "local"`,
overridable with `COEUS_SEED_DEMO_CONTENT`). Loaded once on a fresh dataset
(no tickets yet), so it never duplicates or resets user activity on a
persisted store.

- **Store catalogue** (`repositories/demo_catalogue*.py`): ~43 products spread
  across the themed need-to-know ACGs (region x discipline). The base set maps
  each region/discipline to a canonical product type; a showcase set adds every
  other type explicitly, so the catalogue covers all eight canonical product
  types — standardised assessment reports, intelligence summaries, satellite
  imagery products, geographic (GeoJSON overlay) products, database extracts,
  SIGINT datasets, multi-asset product bundles and fused finished outputs.
  Each product carries type-appropriate assets with the right `preview_kind`
  (PDF, image, GeoJSON, data table; bundles carry several), a geospatial layer
  reference for GeoJSON products, plus classifications, time periods, regions,
  tags and semantic labels, and their placeholder asset bytes.
- **Need-to-know memberships** (`services/demo_seed.py`): the demo customer,
  colleague, RFA manager/team, analyst and QC manager are granted membership
  in every demo-product ACG so the store, RFI search and analyst linking are
  populated for the roles a demo uses.
- **Demo tickets** (`repositories/demo_tickets*.py`): one ticket per workflow
  state (draft, RFI offered/no-match, JIOC review, collect choice, analyst
  assignment, in progress, manager approval, QC review, rework, delivered,
  closed, existing-accepted, cancelled). Each carries the sub-records its
  queue and panels expect (approved routing decision, analyst assignment,
  complete work packages, draft, QC decision, dissemination and feedback),
  assembled from the same record builders the live services use.
- **Feedback + analytics**: the delivered and closed tickets carry
  disseminations and submitted feedback, so the RFA/CM/admin analytics
  dashboards show real product-reuse and satisfaction figures.
- **Team calendars** (`repositories/demo_calendar.py`): availability entries
  spread across each seed team's members and the coming days, so the My Team
  availability tiles and the assignment-panel free-analyst counts are
  realistic.

## Test isolation

Every automated suite asserts exact queue, store and analytics contents, so
the demo dataset must not load in tests. `conftest.py` forces
`COEUS_SEED_DEMO_CONTENT=false` for the whole test process; only
`test_demo_seed.py` opts in (with `environment="local"`) to verify the
dataset populates every queue, the store, analytics and calendars, and to
cover the generators.

## Idempotency and refreshing

The catalogue and its memberships upsert on every boot but short-circuit once
loaded (a marker product and existing memberships are detected), so an
existing local database also picks up catalogue changes on the next restart
without duplicating. Demo tickets and calendar entries seed only on a fresh
dataset (no tickets yet), so workflow progress and user-added entries are
never reset. To reseed the tickets/calendars on a database that already has
tickets, clear the local state (delete `.local-data/` for file/object storage,
or drop the `coeus_state` rows / database for postgres) and restart.

## Non-goals

- No committed JSON database dump; the generators are the source of truth.
- Demo content never loads outside local unless `COEUS_SEED_DEMO_CONTENT` is
  set explicitly.

# Workspace productivity

## Purpose

Workspace productivity features help analysts and managers return to useful
board configurations, reuse approved package structures and notice changes to
their own work. They do not create a second workflow or access-control system.

## Delivered scope

- An actor can create, update, list and delete their own saved board views.
  Filters use the board's allowlisted scope, status, team, priority and date
  fields. Duplicate or oversized values fail validation.
- A manager with a current, version-matched `workspace:configure` grant can
  create, update and delete reusable package templates for an authorised team.
- A user can read and acknowledge privacy-minimised work updates and choose
  immediate or digest delivery, with an independent due-reminder preference.
- A task or work package can carry an opaque link to a Store project or product.
  Creating the link checks both the current task boundary and the existing
  Store project/product policy. Listing it checks both boundaries again.

Store links grant no access. The relational workspace stores only the source
and target identifiers, a presentation label, ownership and version. It does
not copy project membership, ACGs, clearance or product policy. If a user loses
target access, the link is omitted. Direct navigation still uses the existing
Store endpoint, which returns its generic not-found response after a fresh
policy check.

## API and data bounds

The `/api/v1/organisation` API exposes saved views, package templates, Store
links, work updates, acknowledgements and delivery preferences. Lists use UUID
keyset cursors, accept at most 100 rows and never accept an arbitrary user ID.
The work-update response omits recipient and producer event keys.

Every mutation requires CSRF validation, an actor-scoped idempotency key and
expected aggregate version. Team templates additionally bind the exact grant
ID and version. PostgreSQL commands execute at `SERIALIZABLE`, append audit and
outbox evidence in the same transaction and reject mutation of command records.

Saved views and Store links are hidden when their current board, task or Store
authority no longer resolves. Work updates are returned only while the current
recipient can still view both the team and referenced object. Inaccessible
identifiers use the generic workspace-record not-found posture.

## User interface

The task board contains collapsed **Saved board views** and **Package
templates** panels. The profile workspace contains a collapsed **Work updates**
panel. These panels load only when opened, expose loading and empty states, and
use semantic controls suitable for keyboard and screen-reader use.

## Acceptance evidence

- Domain tests cover filter, template and command bounds.
- API tests cover actor-scoped contracts, CSRF and generic not-found handling.
- Real PostgreSQL tests cover idempotent delivery, acknowledgement and
  revocation of task authority.
- Store-link tests prove current labels are re-resolved and links disappear
  immediately after target access is revoked.
- Frontend tests cover lazy loading, applying saved filters, creation journeys
  and automated accessibility checks.

# ADR 0048: Separate projects and subscriptions from personal folders

## Status

Accepted

## Context

The Intelligence Store has private folders whose only responsibility is keeping
personal product references. Extending those folders with membership, research
notes, questions, activity and saved searches would combine unrelated authority
and lifecycle rules.

## Decision

- Keep personal folders private and lightweight.
- Model Projects as collaborative, membership-scoped research spaces.
- Model Subscriptions as private saved search criteria, not alerts and not stored
  result sets.
- Treat selected ACGs as a restrictive search scope, never as authority. The
  selection endpoint returns only the user's active memberships, subscription
  writes validate membership again, and Store search intersects the selection
  with current visibility before retrieval.
- Store only product identifiers in personal libraries and projects. Resolve
  products through the Store detail policy at every response boundary.
- Persist project and subscription aggregates through the existing `StateStore`
  boundary. Production therefore uses guarded PostgreSQL JSONB state and local
  tests use the same service behaviour with in-memory state.
- Project membership grants access to project context only. It never changes
  ACG membership, clearance, product status or Store access policy.
- Return `404` for projects and subscriptions outside the actor's scope.

The Store-scoped project model intentionally supersedes the broad token ban
left by the retired legacy workspace experiment. The legacy top-level
`/api/v1/projects` contract, schema column and suggested-project intake remain
forbidden. The new contract exists only below `/api/v1/store/projects`, uses the
existing Store access policy, and does not restore the retired workspace.

## Consequences

- Product access revocation takes effect immediately in Projects and
  Subscriptions.
- ACG administrators cannot subscribe to a group solely because they can
  administer its metadata; they need an active membership grant.
- The first release does not require a scheduler or notification provider.
- Aggregate limits are required because guarded JSONB state is deliberately
  bounded.
- A future high-volume implementation can move the same service boundary to
  relational project and subscription repositories without changing API rules.

# ADR 0030: Bounded Self-Service And Analyst Context Projections

## Status

Accepted, 2026-07-14.

## Context

The customer ACG page rendered a full application form for every catalogue
entry, profile editing was buried beneath the team workspace, and analyst task
responses exposed only a four-message summary. Adding every transcript to the
analyst task list would multiply a bounded but potentially large conversation
across up to 100 tasks. Relaxing the ACG administrator directory would expose
more identity data than a requester needs.

## Decision

1. The active ACG catalogue owns bounded server-side text search. Filtering is
   applied before pagination and totals. Catalogue items include only current
   manager display names, never usernames, IDs or member rosters.
2. ACG application, withdrawal and review keep their existing endpoints and
   controls. The frontend presents one selected group and one application form
   at a time.
3. Profile editing moves to a dedicated authenticated route and reuses the
   existing self-profile GET and PUT endpoints. Identity and authority remain
   read-only.
4. Full customer conversation history is a separate analyst endpoint resolved
   through the assignment-aware task-detail service. The frontend fetches it
   only after the analyst expands the disclosure.
5. The border-glow treatment is a local CSS effect, not a new runtime
   dependency. It is limited to a single operational focus and reduced-motion
   users receive a static treatment.

## Consequences

- Search totals cannot leak inactive ACGs, and ordinary users see only the
  identity detail required to direct an application.
- Task-list and manager responses remain bounded and compatible.
- Reassignment revokes conversation access through the same object-level rule
  as all other analyst task detail.
- The profile route is available to every authenticated role without coupling
  profile maintenance to team membership.
- The UI gains a reusable restrained focus effect without a package or licence
  dependency.

## Rejected alternatives

- Client-only filtering over the first catalogue page, because it would claim
  global search while silently omitting later groups.
- Relaxing the administrator roster endpoint, because it exposes unnecessary
  account identifiers.
- Embedding transcripts in every analyst task response, because list responses
  could grow by many megabytes.
- Copying a third-party animated component package, because the required effect
  is small, dependency-free and already covered by project motion tokens.

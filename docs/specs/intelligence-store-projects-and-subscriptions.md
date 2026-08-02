# Intelligence Store projects and subscriptions

## Purpose

Give authorised users durable ways to organise intelligence beyond a single
personal folder. Projects provide collaborative research context. Subscriptions
save a controlled Intelligence Store search for repeated use without implying an
external alerting or notification service.

## User experience

The Intelligence Store exposes four clear workspaces:

1. **Discover** keeps search, filters, facets and ranked product results central.
2. **My Library** contains the user's private saved products and folders.
3. **Projects** contains collaborative research spaces and their authorised
   product references, members, notes, questions and activity.
4. **Subscriptions** contains named saved searches with a daily, weekly or
   manual review cadence. Opening a subscription runs its search against current
   holdings and current authority.

Personal folders remain private and intentionally simple. A Project is not a
folder and never grants access to a product.

## Projects

- Any authenticated Store user can create a project.
- A project has a name, purpose, optional region, optional coverage dates and an
  active or archived state.
- The creator is the owner and initial member.
- Owners can add active users by exact username and remove non-owner members.
- Members can add or remove products they can currently open, and add bounded
  notes or intelligence questions.
- Only project members can discover or open the project. Unknown and
  unauthorised project identifiers return `404`.
- Product references are many-to-many: one product may appear in several
  projects without duplicating product content.
- Every response rechecks product access. Hidden product identifiers, titles,
  counts and product-specific activity are not returned.
- Project mutations are CSRF protected, bounded and audited.

## Subscriptions

- A subscription is owned by one user and cannot be shared.
- It has a name, cadence and the same bounded criteria as Store search: query,
  product type, region, tag, source type and coverage dates.
- At least one search criterion is required.
- A user can enable, pause, update and delete a subscription.
- Opening a subscription navigates to Discover and runs the criteria against
  current products and permissions. Stored results or product counts are not
  exposed.
- No email, push or background delivery is introduced in this release.
- Subscription mutations are CSRF protected, bounded and audited.

## Limits

- 25 projects owned per user.
- 50 memberships per project.
- 500 product references per project.
- 200 notes or questions per project.
- 50 subscriptions per user.
- Project names, subscription names and regions are at most 80 characters.
- Purpose and note bodies are at most 2,000 characters; questions are at most
  500 characters.

## Acceptance criteria

- Store navigation makes Discover, My Library, Projects and Subscriptions
  understandable without technical terminology.
- Users can create and use projects and subscriptions without leaving the Store.
- An unrelated user cannot list, read or mutate a project.
- Project membership never grants product access.
- A member who loses product authority no longer sees that product in a project.
- Cross-user subscription identifiers return `404`.
- Mutation failures do not persist unaudited state.
- Backend and frontend line and branch coverage remain at least 95 per cent.

## Deferred

- External delivery channels and scheduled workers.
- Geospatial rendering beyond product region and coverage information.
- Generated briefing documents, comparison matrices and automatic gap analysis.
- Project links to live RFI, RFA and collection workflow records.

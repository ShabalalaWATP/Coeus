# Spec: Admin Command Centre And Operational Analytics

## Purpose

Make the administration workspace compact, legible and operationally useful. Configuration
controls must expose their current state without requiring every section to remain open, and
administrators must be able to return to the command centre from each linked workspace.

## Scope

- Convert access requests, AI provider, search and embeddings, and optional voice configuration
  into accessible collapsible sections.
- Keep a concise status summary visible while each section is collapsed.
- Distinguish a saved API key from an active capability and from a successful connection test.
- Add equivalent connection tests for the independent embeddings and voice integrations.
- Replace flat grey configuration fields with a consistent dark, high-contrast control style.
- Add an admin-only return link to Access Groups, Analytics, Audit, Users and Store.
- Separate administration analytics from intelligence workflow analytics. Admin sees aggregate
  account, access, AI service, search, voice, audit and process health; RFA and Collection retain
  authorised workflow, feedback and reuse analytics.

## Behaviour

### Admin disclosures

- Each configuration section uses a keyboard-operable native disclosure.
- The collapsed summary identifies the section and presents the most useful current state.
- Loading and error states remain available inside the section and are announced accessibly.
- Collapsing a section never cancels or resets a configuration mutation.

### Provider and key state

- Text chat shows the live provider and model, and whether the selected provider has a saved key.
- Search shows its active provider/model, saved-key state and index state.
- Voice shows whether its dedicated key is saved and whether Realtime voice is active or disabled.
- A configured key is described as **saved**, not proven active. A successful test is reported only
  after the relevant test endpoint succeeds.
- API key values remain write-only and are never returned, logged or rendered.
- Search, chat and voice credentials remain independent encrypted secrets.

### Connection tests

- Search keeps its existing provider/model connection test.
- Voice gains an admin-only, CSRF-protected connection test using the configured OpenAI Realtime
  key and selected model.
- The test performs a bounded provider request, returns only a sanitised result and does not enable
  voice or change the saved model.
- Missing keys and provider failures produce a clear non-secret-bearing failure result.

### Admin return navigation

- Users with `system:configure` see a **Back to Admin** link on Access Groups, Admin Analytics,
  Audit, Users and Store.
- Other authorised users can continue to use those workspaces but do not see the admin shortcut.

### Analytics

- Admin analytics uses a dedicated aggregate-only API contract. It contains no ticket, product,
  query, title, reference, username, actor ID or raw audit metadata.
- Admin metrics cover current account state, pending registrations, role distribution, retained
  sign-in and security events, assistant chat turns, RFI search runs, voice session starts and the
  current AI/search/voice configuration.
- Audit-derived values declare the retained 30-day window and whether the retention limit has been
  reached. Provider admission counts are labelled as process-lifetime signals.
- Assistant chat turns are not presented as provider calls or token usage. Accurate provider cost,
  token, latency and embedding-call analytics require a future durable low-cardinality projection.
- RFA and Collection dashboards retain workload, route, feedback, search and product-reuse detail
  under their existing audience permissions.
- Derived team rates use only returned aggregates, clamp visual values and handle zero denominators.
- Progress indicators expose visible percentages and accessible progress semantics.
- Empty, loading and error states remain useful and accessible.

## Security And Privacy

- Existing permission checks remain authoritative at both route and API boundaries.
- Provider tests are administrator-only and require CSRF validation.
- Admin analytics returns aggregate platform signals only and cannot expose ticket or product
  detail. Team analytics remains route- and permission-scoped.
- Provider errors are sanitised before returning to the browser.
- The UI never infers that a saved key has been successfully validated.

## Acceptance Criteria

1. All four admin configuration areas can be expanded and collapsed with keyboard and pointer.
2. Each collapsed area shows an accurate status summary.
3. Search and voice both expose working **Test connection** actions with success and failure states.
4. Key state is visibly and correctly labelled across text chat, search and voice.
5. Admin-only return links exist on every workspace linked from the admin overview.
6. Admin analytics exposes account, AI service, search, voice and security aggregates without
   intelligence detail; RFA and Collection analytics retain their operational scope.
7. Frontend and backend tests cover the new states, access control and connection-test behaviour.
8. Line limits, linting, type checks and the repository coverage gates pass.

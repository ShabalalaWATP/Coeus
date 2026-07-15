# Customer Experience And Analyst Context

## Status

Approved for implementation (2026-07-14).

## Goal

Replace customer-facing card and form walls with a calm operational workspace,
make access-group discovery and profile editing clear, and give an assigned
analyst the complete customer conversation without widening task-list responses
or access boundaries.

## Visual direction

- Use flat, aligned surfaces with strong type hierarchy and one cyan focus edge.
- Use a restrained animated border glow only on the current primary action or
  focused workspace. It must not communicate state by itself and must respect
  reduced-motion preferences.
- Prefer ledgers, rows and disclosure panels over decorative card grids.
- Use modern labelled controls with visible focus, helpful limits and clear
  disabled, error and saved states.

## Customer requests

- Replace the five-card metric mosaic with one compact status ledger.
- Make requests requiring customer action visually primary while keeping total,
  draft, active and delivered counts scannable.
- Keep the request list dominant and preserve released-product and
  delivery-confirmation actions.
- Keep icons and labels on a shared alignment grid at desktop and mobile widths.

## Conversational intake

- Present the surface as a conversation with Istari, with assistant messages
  visually quieter than customer messages.
- Keep the composer, dictation privacy notice, validation, closed and read-only
  states accessible.
- Do not show the intake completeness checklist in the customer workspace.
  Readiness remains a backend rule and manual editing remains available where
  authorised.

## Access groups

- Show every active ACG through a bounded, searchable server-side catalogue.
- Search code, name and description case-insensitively before pagination.
- Every result shows Member, Not a member or the current application status.
- Selecting one result opens a single detail panel containing its description,
  current manager display names and the applicable request or withdrawal action.
- Manager projection is display-name-only. It does not expose usernames, IDs,
  member rosters, inactive groups or product access.
- Justification is 10 to 500 trimmed characters. Existing CSRF, duplicate,
  self-decision, audit and rollback controls remain authoritative.

## Profile

- Every active user can open a dedicated profile page from the profile menu.
- Identity, username and roles are read-only. Title, up to eight specialisms and
  biography use the existing self-profile endpoint.
- The page starts in read mode. Edit profile enables controls; Save commits and
  returns to read mode; Cancel restores the persisted values.
- Profile text remains descriptive and cannot grant roles, clearance, team or
  ACG membership, product access or assignment eligibility.

## Analyst conversation

- Analyst task detail includes a closed-by-default Request conversation
  disclosure after the task context.
- Opening it lazily requests the full ordered customer and Istari transcript.
- The endpoint authorises every request through current assignment and analyst
  task visibility. Reassignment or workflow exit revokes access immediately.
- Transcript content is rendered as plain text. Agent runs, prompts, safety
  flags, internal timeline entries and unrelated workflow data are excluded.
- Task-list and shared manager task projections retain their compact summary and
  never acquire the full transcript.

## Accessibility and responsive behaviour

- Search, disclosure, edit, cancel, save, apply and withdraw controls are fully
  keyboard operable with visible focus.
- Status never depends on colour or animation alone.
- Reduced-motion users receive a static border and immediate content changes.
- Layouts collapse to one column without horizontal overflow at 320 CSS pixels.

## Acceptance criteria

- Customer checklist items are absent from the customer request workspace.
- Request status counts and request actions remain correct and test-covered.
- ACG search filters before totals and excludes inactive groups.
- A customer can select a group, see manager names and submit or withdraw an
  application from one focused detail panel.
- Profile read, edit, save, cancel, validation, loading and error states work for
  every authenticated role.
- Only the currently assigned analyst can expand and read the full transcript.
- Hostile-looking transcript text is displayed inertly, never interpreted as
  markup or instructions.
- OpenAPI and generated TypeScript contracts are current.
- Frontend and backend line and branch coverage remain at least 95 per cent.
- The 350-line limit, lint, type checks, production build and real-browser
  customer and analyst checks pass.

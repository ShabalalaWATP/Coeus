# Frontend Developer Boundaries

Feature components render state and interactions. Keep API transport in
`src/lib/api-client`, server state in TanStack Query hooks, permission decisions
in `src/lib/permissions`, and reusable mutation orchestration in focused hooks.
Do not fetch directly from a page or duplicate backend role logic in JSX.

Generated declarations in `src/lib/api-client/generated/openapi.ts` are the API
schema source. Compatibility aliases may give components stable ergonomic
names, but handwritten transport types must not drift from the generated
contract.

Every asynchronous view handles loading, empty, success and safe error states.
For `409`, refresh server state without losing the user's draft. For `413` and
`429`, retain input and explain the supported recovery. Mutations must prevent
accidental duplicate submission while allowing a deliberate retry.

Use semantic HTML, explicit labels, keyboard operation and visible focus.
Dialogs trap focus while open and restore it to the trigger. Do not add ARIA
when native elements already express the behaviour.

Run format, lint, TypeScript, Knip, Vitest with coverage, production audit and
build. Security or cross-role changes also run the Playwright journey. Keep
components and hooks below the repository line gate; split presentation from
mutation and mapping logic before the limit is reached.

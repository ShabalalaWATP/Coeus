# Development Story: 7 July 2026 Full-Application Audit

Archived from the main [development story](DEVELOPMENT_STORY.md). Historical
evidence, not current operating instructions.

## 2026-07-07 Full-application audit and remediation

- Ran a three-track audit (frontend, backend, AI agents) that found broken
  functionality, silent failure modes and security gaps; recorded decisions in
  ADR 0015 and `docs/threat-model/audit-remediation.md`.
- Made `COEUS_LLM_PROVIDER` authoritative: an API key never switches the
  provider implicitly, flagged messages are refused on every provider path and
  are no longer extracted, and Gemini failures degrade to the mock reply
  instead of losing the customer's message. Removed the unimplemented gemma
  providers and the empty `agents/` package directory.
- Hardened the prompt-injection scanner (normalisation plus regex marker
  families) and stopped the intake extractor inventing operational questions
  and success criteria, so the completeness checklist reflects only what the
  customer said.
- Fixed the capability agents' tokenisation (punctuation, plurals, the
  "unknown" false positive) and made CM feasibility require a genuine
  collection signal; RFI search now ranks every permitted published product
  instead of the first browse page and 2-character regions such as UK score.
- Closed lifecycle dead ends: added `CLOSED_DELIVERED` with an owner-only
  confirm-delivery endpoint and button, analyst reassignment during
  production, idempotent work-package updates and same-queue route override
  with the override-reason UI.
- QC approval now validates up front, sanitises time periods to ISO dates,
  writes downloadable placeholder bytes at ingestion and rolls back the store
  product if the ticket update fails.
- Security: session IDs hashed at rest, self-service password change with
  forced rotation after admin resets, proxy-aware login throttling with
  lockout decay, need-to-know directory search, asset tokens moved to the
  `X-Asset-Token` header with no-store caching, CSRF on access diagnostics,
  and `TICKET_READ_ALL` no longer confers write access.
- Frontend: a shared mutation-error helper ended the silent-failure pattern
  across routing, analyst, QC, feedback, notifications and upload; global 401
  handling routes to the session-expired page; partial intake saves omit blank
  fields; the QC checklist resets between products; unreachable pages gained
  navigation and deep-link handling; dead components were removed.
- Verified the whole lifecycle in the running app: chat intake with injection
  refusal, RFI search and offer rejection, capability review, same-queue
  approval, analyst production, QC approval, release with notification,
  delivery confirmation and a header-token asset download. The live run
  surfaced and fixed three integration gaps: `X-Asset-Token` missing from the
  CORS allow list, cacheable grant/download responses replaying stale tokens,
  and the routing plan update record missing from the persistence codec
  allowlist.
- Checks: pytest (269 tests, 95.9% coverage), Vitest (280 tests, 99% lines),
  mypy, Ruff, tsc, ESLint, Prettier and the 350-line limit all pass.

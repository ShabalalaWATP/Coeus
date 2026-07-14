# Audit Remediation Threat Model

## Scope

Full-application audit remediation on branch `fix/audit-findings`: LLM provider
control, prompt-injection handling, session and credential hardening, routing
and QC authorisation, asset token transport and need-to-know exposure fixes
across the API and web app.

## Assets

- Customer chat content and extracted intake requirements.
- The Gemini API key and the provider selection state.
- Session cookies, CSRF tokens and persisted session records.
- The staff account directory (usernames are email addresses).
- Asset download tokens and released product bytes.
- Ticket state, routing decisions and QC release decisions.

## Threats And Controls

| Threat | Control |
|---|---|
| An environment-supplied Gemini key silently sends customer chat to an external API while the operator configured `mock`. | `COEUS_LLM_PROVIDER` is authoritative. A key alone never switches the provider; only explicit configuration (setting or admin API) selects `gemini_api`. Unimplemented gemma providers were removed from configuration. |
| Prompt-injection text reaches the external model or durable ticket state. | Safety scanning normalises messages (casefold, zero-width strip, whitespace collapse) and matches regex marker families. Flagged messages get the fixed refusal on every provider path, are never sent to Gemini and are never extracted into intake fields. |
| A Gemini outage or missing key breaks intake capture and drops customer messages. | Provider errors degrade to the deterministic mock reply; the customer message, flags and reply are always persisted. Logs carry error codes only, never keys or message content. |
| Any authenticated user enumerates the full staff roster. | The user directory requires a search term of three or more characters and returns at most ten active accounts, excluding the caller. |
| A database backup or state file replays live sessions. | Session identifiers are stored as SHA-256 hashes at rest; the raw token exists only in the cookie and login response. |
| A forged forwarded address bypasses throttling, or denied attempts grow memory without bound. | Forwarded addresses are accepted only when both `COEUS_TRUSTED_PROXY_COUNT` and matching `COEUS_TRUSTED_PROXY_CIDRS` identify the socket peer. Username and source histories decay, have fixed entry ceilings and never append denied attempts. |
| Credentialed cross-origin requests are exposed by wildcard or malformed origins. | Startup rejects wildcards, credentials, paths, queries, fragments and non-HTTP(S) values in `COEUS_ALLOWED_CORS_ORIGINS`. |
| Admin-reset credentials remain in long-term use. | Admin resets set `password_reset_required`; all endpoints except me/logout/password-change return 403 until the user changes the password via the new CSRF-protected self-service endpoint, which rotates the session and invalidates all others. |
| A concurrent credential operation revives a revoked session. | Password change and administrative reset advance a persisted credential version. Session validation rejects older versions, while rotation atomically consumes its source. |
| Logout audit failure restores authority to preserve audit atomicity. | Logout is the deliberate exception to compensation: once the session is revoked it is never restored. Audit failure fails the HTTP request and triggers the browser's unconfirmed-retry state, but cannot resurrect authentication authority. |
| Asset download tokens leak through access logs, proxies or browser history. | Tokens moved from the URL query string to the `X-Asset-Token` request header; the web app downloads via fetch and blob. Token HMAC binding and 15-minute expiry are unchanged. |
| A manager approves a route for a queue they do not manage by supplying an override reason. | Route approval requires the review permission of the queue the ticket currently sits in; the override reason remains required off-recommendation. |
| A read-scoped role silently gains ticket write access. | `TICKET_READ_ALL` no longer confers write. Writes require ownership, editor collaboration or the explicit `TICKET_WRITE_ALL` permission. |
| Free-text metadata crashes QC approval and leaves an orphaned draft product. | Time periods are ISO-date constrained at the schema boundary, sanitised on QC copy, and approval validates up front and rolls the product back if the ticket update fails. |
| Concurrent or partially failed QC release publishes a product without matching ticket and audit state. | PostgreSQL relational mode locks and version-checks the ticket, then commits ticket, Store projection, audit evidence and a uniquely keyed notification intent in one transaction. Forced-failure and two-worker tests prove rollback and one-winner behaviour. |
| Ticket creation or a staff workflow update commits without its audit evidence. | `TicketMutationService` selects collision-safe create or version-checked update operations. PostgreSQL commits the aggregate, shadow event and audit evidence on one connection; local modes retain the tested compatibility path. |
| Symmetric related-ticket linking updates only one side or loses its audit event. | The paired transaction locks both ticket IDs in deterministic order and commits both aggregates and audit evidence together. A stale side rolls the complete unit back. |
| An outbox retry duplicates a release notification after a worker crash. | The durable event ID is reused as the in-app notification and email record ID, so replay returns existing records. Malformed or inactive-requester intents fail into bounded retry and dead-letter handling. |
| An outbox uniqueness collision hides different release content. | The release transaction reads back the stored deterministic event and payload. A different event ID or payload for the same ticket version fails the whole transaction closed. |
| Local multi-event or paired mutations leave partial evidence or asymmetric state. | Memory and file modes append audit batches as one store operation and replace paired tickets under one repository lock. Hosted multi-process use remains PostgreSQL-only. |
| Store search filters act as wildcards. | `%`, `_` and `\` are escaped in ILIKE patterns; date filters parse ISO values and ignore invalid input. |
| The one CSRF-exempt POST endpoint is used for request forgery. | Access diagnostics now requires the CSRF-validated session like every other mutating route. |

## Accepted Risks And Deferred Items

- The in-memory and file whole-namespace models remain single-worker only.
  Hosted PostgreSQL relational mode is the multi-process authority. Ticket
  creation, single-ticket workflow updates, paired links and QC release use the
  workflow transaction port; coordinated restore proof remains outstanding.
- Memory and file audit caches remain bounded to 10,000 events. PostgreSQL uses
  the durable audit event table; retention and archival policy remain an
  operational decision.
- CSRF tokens remain raw in session records because `/auth/me` must return
  them; they are useless without the hashed session cookie.
- Intake fields cannot be cleared through PATCH once set (nulls are filtered);
  a clear-field sentinel is future work.

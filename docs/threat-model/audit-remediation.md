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
| A shared proxy IP triggers an organisation-wide login lockout, or a trickle of failures keeps an account locked forever. | `COEUS_TRUSTED_PROXY_COUNT` (default 0) controls X-Forwarded-For trust explicitly; per-username failure records decay once older than the lockout window. |
| Admin-reset credentials remain in long-term use. | Admin resets set `password_reset_required`; all endpoints except me/logout/password-change return 403 until the user changes the password via the new CSRF-protected self-service endpoint, which rotates the session and invalidates all others. |
| Asset download tokens leak through access logs, proxies or browser history. | Tokens moved from the URL query string to the `X-Asset-Token` request header; the web app downloads via fetch and blob. Token HMAC binding and 15-minute expiry are unchanged. |
| A manager approves a route for a queue they do not manage by supplying an override reason. | Route approval requires the review permission of the queue the ticket currently sits in; the override reason remains required off-recommendation. |
| A read-scoped role silently gains ticket write access. | `TICKET_READ_ALL` no longer confers write. Writes require ownership, editor collaboration or the explicit `TICKET_WRITE_ALL` permission. |
| Free-text metadata crashes QC approval and leaves an orphaned draft product. | Time periods are ISO-date constrained at the schema boundary, sanitised on QC copy, and approval validates up front and rolls the product back if the ticket update fails. |
| Store search filters act as wildcards. | `%`, `_` and `\` are escaped in ILIKE patterns; date filters parse ISO values and ignore invalid input. |
| The one CSRF-exempt POST endpoint is used for request forgery. | Access diagnostics now requires the CSRF-validated session like every other mutating route. |

## Accepted Risks And Deferred Items

- The in-memory, whole-namespace JSON persistence model is single-worker only.
  Running multiple workers or instances remains unsafe and is a documented
  deployment constraint pending a relational persistence redesign.
- The audit log remains a bounded ring buffer (10,000 events); oldest events
  are discarded at capacity. A durable audit store is future work.
- CSRF tokens remain raw in session records because `/auth/me` must return
  them; they are useless without the hashed session cookie.
- Intake fields cannot be cleared through PATCH once set (nulls are filtered);
  a clear-field sentinel is future work.

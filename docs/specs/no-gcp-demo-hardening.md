# No-GCP Demo Hardening

## Scope

Complete local-first improvements that do not require Google Cloud now or later:

- Admin credential reset for local/test managed users.
- Stronger deterministic intake extraction.
- Store pagination for scalable browsing of synthetic products.
- A full mocked Playwright workflow covering request to final release.

Persistence, object storage, email transport and Gemini API work are covered by
`local-persistence-files-llm-email.md`.

## Acceptance Criteria

- Administrators can reset another user's credential from `/admin/users`.
- Reset credentials are generated server-side, returned once, never written to
  audit metadata and revoke the target user's active sessions.
- Natural request phrasing captures routine priority, deadlines, regions,
  output formats and success criteria without manual edits.
- Store search accepts `page` and `pageSize`, returns pagination metadata and
  keeps facets and totals scoped after access checks.
- Store UI exposes previous/next pagination controls and sends page parameters.
- Playwright covers the main customer, RFA manager, analyst, QC and release
  screens with deterministic API mocks.

## Non-Goals

- Database-backed user storage.
- Real file byte upload or download.
- Production email provider integration.
- Cloud Run, Cloud SQL, GCS or cloud AI changes.

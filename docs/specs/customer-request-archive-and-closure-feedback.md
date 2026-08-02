# Customer Request Archive and Closure Feedback

## Status

Approved for implementation (2026-08-01).

## Problem

The customer dashboard presents open, closed and cancelled requests in one
register. A long history makes current work difficult to scan and can make a
customer believe that every visible record is still open.

Feedback is also presented as a permanent queue separate from the request it
describes. The form exposes a numerical selector, a mandatory comment and a
follow-up flag before the ticket has necessarily closed. This duplicates the
existing product-outcome and re-analysis workflow and permits feedback against
work that is still active.

## Behaviour

### Request register

- The primary register contains only draft and active requests.
- Closed and cancelled requests appear in a separate disclosure immediately
  after the primary register.
- The disclosure is collapsed by default and states how many loaded requests
  it contains.
- Opening the disclosure reveals the same reference, title, state, update date
  and authorised links available in the primary register.
- Summary counts distinguish open, draft, in-progress and closed work. Closed
  includes cancelled records for dashboard organisation, while feedback
  remains limited to states whose value begins with `CLOSED_`.
- Pagination continues to operate over the server-provided chronological
  result set. Counts describe the pages currently loaded.

### Feedback

- The API lists a feedback request to its requester only when the associated
  ticket is in a `CLOSED_*` state.
- The API rejects direct submission while the ticket remains open, even when a
  feedback request was prepared during product release.
- The dashboard presents only the newest pending closed-ticket feedback item.
  Completing it advances to the next pending item rather than displaying a
  stack of forms.
- The prompt names the ticket reference and delivered product, then asks how
  well the product answered the request.
- The customer chooses one of three clear outcomes: fully, partly or not at
  all. These retain the existing analytics values 5, 3 and 1.
- An explanatory note is optional. Follow-up is not requested through this
  form because unmet work is handled before closure by the product-outcome and
  re-analysis workflow.
- Submitted feedback remains immutable and contributes to the existing
  role-scoped analytics.

## Security and integrity

- Existing ticket visibility and `feedback:create` permission checks remain in
  force.
- Closure is checked by the service at submission time, not trusted from the
  browser.
- A requester can still submit each feedback request at most once.
- Feedback remains scoped to the original requester, ticket and product.
- No protected ticket content is added to the list response.

## Acceptance criteria

- Closed and cancelled tickets are absent from the open register on first
  render.
- The closed-request disclosure is collapsed by default and keyboard
  operable.
- Opening the disclosure reveals the archived records and their existing safe
  actions.
- An open ticket's feedback request is neither listed nor accepted for
  submission.
- Closing the ticket makes its pending feedback available.
- The simplified form submits the selected outcome and optional note without a
  follow-up control.
- Empty feedback state does not add a permanent panel to the dashboard.
- Backend and frontend line and branch coverage remain at or above 95 per cent.

## Related documentation

- [Sprint 11 feedback and analytics](sprint-11-feedback-analytics.md)
- [ADR 0012: Local-first feedback analytics](../adr/0012-local-first-feedback-analytics.md)
- [ADR 0044: Closure-gated customer feedback](../adr/0044-closure-gated-customer-feedback.md)
- [User guide](../USER_GUIDE.md#customer)

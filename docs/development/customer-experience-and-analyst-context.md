# Customer Experience And Analyst Context

## 2026-07-14 delivery

- Replaced the customer metric-card mosaic with an aligned status ledger and
  operational request register, with restrained token-based border glow for
  attention states.
- Simplified request intake to the customer and Istari conversation, removed
  the internal completeness checklist from the customer surface, and retained
  explicit manual editing as progressive disclosure.
- Added server-side ACG search, visible membership state, selected-group detail,
  a minimal active-manager projection and a modern application form.
- Moved self-profile editing to a dedicated read-first account page with
  explicit edit, cancel and save states for every signed-in user.
- Added lazy, assignment-authorised full chatbot history to analyst task detail
  without expanding task-list payloads.

## 2026-08-01 refinement

- Kept the primary customer register focused on draft and active work, with
  completed and cancelled requests in a native disclosure collapsed by default.
- Replaced the permanent feedback queue with one sequential prompt that names
  the closed ticket and product, asks whether it answered the request and
  accepts an optional learning note.
- Enforced ticket closure in the feedback service for both listing and direct
  submission, while preserving immutable feedback analytics.

Verification evidence is tracked in `docs/MASTER_IMPLEMENTATION_PLAN.md` and
the acceptance contract is `docs/specs/customer-experience-and-analyst-context.md`.

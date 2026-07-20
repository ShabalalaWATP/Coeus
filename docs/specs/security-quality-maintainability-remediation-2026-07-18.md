# Security, Quality And Maintainability Remediation

## Status

Implementation complete on 18 July 2026, with final full-suite and PostgreSQL
release evidence in progress. This remains release-blocking until every
acceptance gate below is recorded as passing.

## Evidence Baseline

The baseline is Codex Security scan `f570ef86-fbcb-4eeb-8778-e836ec7130ac`
against Git revision `5f6066e83e340c40066e5d8ed0a70a1c80564f54` and working-tree snapshot
`codex-security-snapshot/v1:sha256:88cb9abaa2c37da7dc1c9791f18e9fb379c6d9c7acbbd588d2c1e5a0fda61df2`.
The snapshot contained 269 changed paths, including 79 untracked files. The
working tree, rather than the revision alone, is therefore the implementation
baseline.

The scan reported three medium-severity findings, one low-severity finding,
35 failing backend tests, and maintainability defects across backend and
frontend boundaries. Frontend tests passed at 98.64 per cent line coverage and
95.06 per cent branch coverage. Backend coverage exceeded 95 per cent, but the
failing assertions make that result non-releasable.

## Outcomes

- Password change cannot overwrite a concurrent account disable, role change,
  clearance change or credential reset.
- A committed account-security change, session revocation, replacement session
  and audit record have one current-state confirmation boundary.
- Expired sessions are pruned and retained sessions have explicit per-user and
  deployment-wide limits.
- Workflow draft bytes are disclosed only after live object, route,
  assignment, role, clearance and ACG authorisation.
- `TICKET_READ_ALL` and `PRODUCT_APPROVE` are never sufficient draft-content
  authority.
- The customer status projection represents `RFI_NO_MATCH` as actionable.
- Backend and frontend contracts, query identity and protected-data lifetime
  are explicit and testable.
- Service code is independent of FastAPI application state and external
  providers are injected through narrow ports.
- Complexity and production dead-code gates enforce the repository's stated
  standards.
- The backend and frontend suites pass with at least 95 per cent line and branch
  coverage.

## Security Invariants

### Identity and sessions

1. A password change is accepted only for the exact current account state that
   authenticated the operation.
2. Account mutations preserve unrelated fields and fail with a conflict when
   their expected state is stale.
3. Failed compensation cannot restore an older whole account over a newer
   administrative decision.
4. Session issue prunes expired state, retains at most five sessions per user,
   and retains at most 1,000 sessions for one local deployment.
5. Per-user overflow evicts the oldest session for that user. Deployment-wide
   saturation rejects the new session without evicting another user's session.
6. Session capacity errors use a stable, non-sensitive API response and an
   audit event.

### Protected workflow drafts

Every ordinary preview requires all of the following:

- an active actor with `PRODUCT_READ`;
- sufficient live clearance and active ACG overlap for the selected version;
- exact ticket, version and asset binding;
- a supported workflow state; and
- one current relationship: assigned analyst, responsible same-route area
  manager, or named QC reviewer.

RFA and CM managers are area managers across all active teams of their own
route kind. The selected active team remains authoritative for assignment
ownership, candidate membership and availability, but the manager need not be
a member of that team. Manager preview additionally requires the ticket's
current approved route, a valid active selected-team assignment and the route's
specific review permission.

Platform administrators have no ordinary workflow-draft content access.
`TICKET_READ_ALL` remains ticket catalogue and support visibility only. No
workflow break-glass endpoint will be introduced in this milestone because the
clearance, ACG and state override policy has not been approved. A later feature
must start with its own spec and use a CSRF-protected, reasoned,
audit-before-disclosure operation.

## Correctness And Maintainability Work

### Backend

- Add `RFI_NO_MATCH` to actionable customer-state projection and copy.
- Enable Ruff C901 enforcement and refactor every current violation below the
  configured threshold without weakening behaviour.
- Move FastAPI imports and `app.state` mutation out of service modules and into
  API composition/builders.
- Inject external model, voice and ticket-builder calls through narrow ports or
  constructor callables.
- Replace broad repository dependencies with consumer-specific protocols.
- Preserve the 350-line hard limit and split files that reach the limit when
  touched by this work.

### Frontend

- Treat generated OpenAPI schemas as the source for API response types and
  guard optional fields at render boundaries.
- Give every TanStack query key its complete endpoint identity, including
  route, team and date where applicable.
- Never place credentials, access grants or download tokens in query keys.
- Do not retain protected Blob data beyond the grant lifetime. Revoke object
  URLs on replacement, logout and unmount.
- On HTTP 409, invalidate and reconcile the affected aggregate before accepting
  further edits. On HTTP 413, preserve the user's draft and present a specific
  size error.
- Prevent background refresh from overwriting a locally dirty intake draft.
- Split routing and request mutation hotspots by responsibility.
- Move permission and route decisions into central helpers.
- Add semantic alert and grid behaviour, keyboard coverage and automated
  accessibility checks for the reported gaps.

### Dead code and gates

- Remove code proved unused in production and tests.
- Preserve intentionally dormant capabilities only behind a documented public
  boundary or an explicit Knip entry with an owner and reason.
- Run standard Knip and a production-only Knip configuration in CI.
- Extend the architecture check to reject FastAPI imports in services and raw
  workflow-draft storage reads outside the owned access boundary.

## Defence-In-Depth Follow-up

The scan also validated upload pre-spooling, Office/XML expansion and Windows
restore-staging weaknesses. Their final severity was suppressed only by the
current loopback, authenticated, operator-controlled and synthetic-data
assumptions. This milestone must either repair them or record them as explicit
deployment blockers. They must be re-rated before shared-network, multi-instance
or operational-data use.

## Implementation Sequence

1. Encode the four security findings and the `RFI_NO_MATCH` defect as failing
   regression tests.
2. Add current-state identity mutation and bounded session admission.
3. Add one ordinary protected-draft access policy and deny administrator
   shortcuts.
4. Restore the backend suite, then enable C901 and architecture rules.
5. Repair frontend contract, cache, protected-data, conflict and accessibility
   behaviour.
6. Remove confirmed dead code and enable production dead-code analysis.
7. Update threat models, ADR cross-references, runbooks, implementation plan and
   development story.
8. Run all release gates and a final requirement-by-requirement audit.

## Acceptance Criteria

1. The original password race, session growth, cross-route manager preview and
   administrator preview reproductions fail safely through the real API.
2. Legitimate password change, login rotation, assigned-analyst preview,
   responsible-manager preview and named-QC preview continue to pass.
3. Concurrent account mutations cannot restore unrelated fields or produce an
   authenticated session for an inactive account.
4. Retained session counts never exceed configured limits and expired sessions
   are pruned without requiring presentation of their cookies.
5. Every workflow-draft byte sink uses the owned access decision before storage
   access.
6. `RFI_NO_MATCH` is displayed as actionable and covered by regression tests.
7. Ruff, strict mypy, ESLint, TypeScript, formatting, line-limit, architecture,
   contract, documentation-link and both dead-code checks pass.
8. Backend and frontend tests pass with at least 95 per cent line and branch
   coverage.
9. PostgreSQL integration and concurrency tests pass against the supported test
   stack. If the stack is unavailable, release remains blocked.
10. Dependency audit, secret scanning and the repository security-policy check
    pass.
11. A final review finds no unresolved item from this specification's closure
    ledger.

## Closure Evidence

All acceptance criteria are satisfied for the supported local-first boundary.
The final backend run passed 1,233 tests with one intentional external N-1
source-tree skip, at 98.13 per cent line and 95.15 per cent branch coverage.
The complete frontend run passed 530 tests at 98.65 per cent line and 95.14 per
cent branch coverage. PostgreSQL integration ran on the loopback development
stack. Static analysis, dependency audit, secret scan, architecture, contract,
documentation, security-policy and both dead-code modes pass. The item-by-item
proof is retained in
`docs/security/SECURITY_REVIEW_REMEDIATION_2026-07-18.md`.

The supported boundary has not expanded. Shared-network, multi-instance or
operational-data deployment still requires the malware worker, distributed
admission, managed secret, staging and deployment controls already documented
in the threat models and runbooks.

## Out Of Scope

- A public or multi-instance deployment.
- A general external policy engine or identity microservice.
- An administrator workflow-draft break-glass feature without an approved
  override policy.
- Real intelligence content or operational examples.

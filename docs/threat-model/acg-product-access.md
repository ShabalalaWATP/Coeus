# ACG And Product Access Threat Model

## Scope

ACG membership, self-service access applications, delegated ACG administration,
product access filtering and access diagnostics.

## Assets

- ACG definitions and memberships.
- ACG administrator rosters, application justifications and decision reasons.
- Product metadata visibility.
- Access diagnostic results.
- Audit events for ACG changes.

## Trust Boundaries

- Browser to FastAPI access-control endpoints.
- Frontend route visibility to backend RBAC and ACG enforcement.
- Local seed repository to future database-backed access repository.
- Administrator diagnostics to subject-user access evaluation.

## Threats And Controls

| Threat | Control |
|---|---|
| IDOR against ACG detail | `AccessControlGroupService.get_visible_acg` returns not-found for inaccessible ACGs. |
| Product leakage through Store reads | Store access checks use product RBAC, active ACG overlap, clearance and product status. |
| RBAC bypass through frontend navigation | Backend permission checks and service policies are authoritative. Frontend route guards only shape navigation. |
| Disabled user access | Product policy requires an active user. |
| Inactive ACG revocation bypass | Product policy uses only active ACG memberships when evaluating visibility. |
| Draft product leakage | Draft products require product management permission in addition to ACG membership. |
| ACG membership manipulation | Create, update and membership endpoints require CSRF-validated authenticated sessions and ACG permissions. Non-administrator ACG managers cannot add or remove their own ACG memberships. |
| Delegated administration grants product visibility | Administrator rosters are stored separately from memberships. Adding an administrator grants review authority only and never creates membership. |
| Cross-group application review | Review queues are derived server-side from the actor's current delegated rosters. Platform administrators can review all groups; roster removal revokes delegated review immediately. |
| Self-approval or stale concurrent decisions | Decision handling rejects self-decisions and non-pending records under a single-writer lock. The first valid decision wins; later attempts fail without changing membership. |
| Partial approval creates unaudited membership | Approval compensates workflow and membership changes if persistence or audit recording fails. The current implementation remains explicitly single-writer and does not claim multi-replica transaction safety. |
| Application text leaks through audit | Submission, withdrawal and decision events contain identifiers, status and counts only. Justifications and rejection reasons are excluded from audit metadata and catalogue projections. |
| Unbounded catalogue or review response | Active ACG catalogues, active-user directories and pending review queues use validated page sizes capped at 50. Application text is capped at 500 characters after whitespace normalisation. |
| Catalogue search leaks inactive ACGs | Active-state filtering and bounded case-insensitive search run before pagination and totals, so inactive groups cannot appear through result metadata. |
| Manager projection becomes a user directory | Catalogue items expose active manager display names only. They omit usernames, user IDs and member rosters, and manager status does not imply ACG membership or product access. |
| Administrator roster abuse | Only platform administrators mutate rosters. Candidates must be active users, duplicate and stale mutations fail, active ACGs retain at least one administrator, and the eight-person limit is checked inside the mutation lock. Existing active owners bootstrap previously uninitialised rosters. |
| Broad user-directory disclosure | The ACG directory exposes only active user ID, display name and username, is paginated, and is limited to platform administrators and existing ACG membership managers. Scoped ACG responses expose the same narrow identity fields only for that group's members. |
| Browser-only ACG revocation | The ACG member removal control calls the backend delete endpoint with the session CSRF token. The backend remains authoritative for permission, self-membership and audit enforcement. |
| Store Manager ACG administration leaks content | Users with ACG assignment permissions may see ACG metadata and memberships for administration, but product detail, search and downloads still require product RBAC, active ACG overlap, clearance and status checks. Site-admin support access outside ACGs is separate audited break-glass access. |
| Missing accountability for ACG changes | ACG creation, update, membership addition and membership removal create audit events. |
| Failed audit persistence leaves a hidden ACG change behind | ACG create, update, member-add and member-remove operations restore their previous repository state if audit recording fails. |
| Diagnostic abuse by ordinary users | Product diagnostics require `system:configure` and CSRF validation. |
| Broad demo membership masks broken deny paths | Billy Gilmour belongs to 56 of 58 ACGs but is deliberately excluded from Russia SIGINT and China cyber. Tests assert both the exact matrix and per-product single-ACG assignment. |
| Restart silently restores a deliberately revoked membership | Versioned demo-access reconciliation adds new seed memberships once. Later restarts preserve operator changes instead of reapplying the migration. |

## Open Risks

- ACG administration and applications still use bounded compatibility-state
  repositories in the supported single-process composition. Store products and
  audit evidence use dedicated relational PostgreSQL tables by default.
- Approval compensation protects the supported single-process writer. A future
  multi-replica deployment requires one database transaction spanning the
  application decision, membership change and durable audit outbox.
- Releasability and caveat checks are represented by current metadata fields
  but need richer policy logic when real product metadata is introduced.
- Product assets, downloads and search have their own threat models and
  IDOR-style regression tests.

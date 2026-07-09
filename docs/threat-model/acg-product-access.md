# ACG And Product Access Threat Model

## Scope

ACG membership, product access filtering, ACG administration and access diagnostics.

## Assets

- ACG definitions and memberships.
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
| Browser-only ACG revocation | The ACG member removal control calls the backend delete endpoint with the session CSRF token. The backend remains authoritative for permission, self-membership and audit enforcement. |
| Store Manager ACG administration leaks content | Users with ACG assignment permissions may see ACG metadata and memberships for administration, but product detail, search and downloads still require product RBAC, active ACG overlap, clearance and status checks. Site-admin support access outside ACGs is separate audited break-glass access. |
| Missing accountability for ACG changes | ACG creation, update, membership addition and membership removal create audit events. |
| Failed audit persistence leaves a hidden ACG change behind | ACG create, update, member-add and member-remove operations restore their previous repository state if audit recording fails. |
| Diagnostic abuse by ordinary users | Product diagnostics require `system:configure` and CSRF validation. |

## Open Risks

- ACG, product and audit data use the configured local state store; a
  normalised relational schema with migrations remains future production work.
- Releasability and caveat checks are represented by current metadata fields
  but need richer policy logic when real product metadata is introduced.
- Product assets, downloads and search have their own threat models and
  IDOR-style regression tests.

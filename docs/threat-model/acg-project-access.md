# ACG And Project Access Threat Model

## Scope

Sprint 3 ACG membership, project workspace visibility, product access filtering, ACG administration and access diagnostics.

## Assets

- ACG definitions and memberships.
- Product metadata visibility.
- Project workspace membership, ACG links, ticket links, plan items and product links.
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
| IDOR against project workspaces | `ProjectWorkspaceService.get_visible_workspace` returns not-found for missing or inaccessible projects. |
| Product leakage through project workspace | Project product lists are filtered through `ProductAccessPolicy` for the current user. |
| RBAC bypass through frontend navigation | Backend permission checks and service policies are authoritative. Frontend route guards only shape navigation. |
| Disabled user access | Product and project policies require an active user. |
| Inactive ACG revocation bypass | Product and project policies use only active ACG memberships when evaluating visibility. |
| Draft product leakage | Draft products require product management permission in addition to ACG membership. |
| ACG membership manipulation | Create, update and membership endpoints require CSRF-validated authenticated sessions and ACG permissions. Non-administrator ACG managers cannot add or remove their own ACG memberships, preventing self-grant escalation into project or product visibility. |
| Browser-only ACG revocation | The ACG member removal control calls the backend delete endpoint with the session CSRF token. The backend remains authoritative for permission, self-membership and audit enforcement. |
| Store Manager ACG administration leaks content | Users with ACG assignment permissions may see ACG metadata and memberships for administration, but product detail, search and downloads still require product RBAC, active ACG overlap, clearance and status checks. Site-admin support access outside ACGs is separate audited break-glass access. |
| Project ACG inheritance leaks unrelated QC products | QC ingestion only inherits project ACGs when the ticket is explicitly linked in `project.ticket_ids`; same-requester projects do not implicitly attach to unrelated tickets. |
| Missing accountability for ACG changes | ACG creation, update, membership addition and membership removal create audit events. |
| Diagnostic abuse by ordinary users | Product diagnostics require `system:configure`. |

## Open Risks

- ACG, product, project and audit data use the configured local state store; a
  normalised relational schema with migrations remains future production work.
- Releasability and caveat checks are represented by current metadata fields but need richer policy logic when real product metadata is introduced.
- Product assets, downloads and search have their own later threat models and
  IDOR-style regression tests.

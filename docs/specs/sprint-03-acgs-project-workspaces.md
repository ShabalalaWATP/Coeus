# Sprint 3 Spec: ACGs And Project Workspaces

## Purpose

Add the first project and product visibility layer on top of Sprint 2 RBAC. RBAC decides what a user can do; ACG membership decides what products and project workspaces the user can see.

## Scope

- Local seed models for Access Control Groups, ACG memberships, product summaries and project workspaces.
- Backend services for ACG administration, product access policy, project access policy, project workspace views and access diagnostics.
- API routes for listing, creating, editing and assigning ACG members.
- API routes for listing project workspaces and reading project plan, member and product slices.
- Product access diagnostics for administrators.
- Frontend routes for `/admin/acgs`, `/admin/acgs/:acgId`, `/projects`, `/projects/:projectId`, `/projects/:projectId/plan`, `/projects/:projectId/members` and `/projects/:projectId/products`.
- ACG administration UI for group creation, status updates and user assignment.
- Project workspace UI showing linked ACGs, members, plan items and only permitted products.
- Audit events for ACG creation, update, membership addition and membership removal.

## Non-goals

- Persistent database-backed ACG, product and project tables. These are part of the later database and migration phase.
- Product upload, asset access, search indexing and product detail pages. Those remain Sprint 5 and later.
- Full project creation and edit flows. Sprint 3 exposes project workspace basics and access-filtered reads.
- Real intelligence data. All seeded records are synthetic mock data.

## Access Rules

- Users must be active.
- Users must hold the relevant RBAC permission for the action.
- Product reads require `product:read`.
- Draft product visibility additionally requires product management permission.
- Product visibility requires shared ACG membership unless the user has `product:read_restricted`.
- Project visibility requires project membership, shared project ACG membership or an administrator override.
- ACG list visibility requires `acg:view`; administrators see all ACGs and product-team roles see only their relevant ACGs.
- Missing or unauthorised project and ACG detail reads return not-found style errors to avoid confirming inaccessible IDs.

## Acceptance Criteria

- Users can belong to many ACGs.
- Products can belong to many ACGs.
- Projects can be linked to many ACGs.
- Project workspaces return only products the current user can access.
- Managers can view relevant ACGs without seeing unrelated ACG detail.
- Administrators can create and update ACGs and add or remove ACG members.
- Access diagnostics explain allow and deny outcomes.
- ACG administration changes create audit events.
- Backend and frontend tests cover ACG membership, product policy, project visibility and UI workflows.

## Verification

- Backend: `uv run --directory apps/api ruff format --check src tests`, `uv run --directory apps/api ruff check src tests`, `uv run --directory apps/api mypy src` and `uv run --directory apps/api pytest` passed.
- Backend coverage: 97.04 percent total coverage.
- Frontend: `pnpm --filter @coeus/web format:check`, `pnpm --filter @coeus/web lint`, `pnpm --filter @coeus/web typecheck`, `pnpm --filter @coeus/web test`, `pnpm --filter @coeus/web build` and `pnpm --filter @coeus/web test:e2e` passed.
- Frontend coverage: 100 percent statement, line and function coverage, with 96.03 percent branch coverage.
- Security: `uv run --directory apps/api bandit -r src`, `uv run --directory apps/api pip-audit`, `uv run --project apps/api semgrep scan --config auto --error apps/api/src apps/web/src infra/docker .github` and `pnpm --filter @coeus/web audit --prod` passed.
- Infrastructure: `docker compose config` passed.

# Sprint 3 Spec: ACGs And Product Access

## Purpose

Add the first product visibility layer on top of Sprint 2 RBAC. RBAC decides what a user can do; ACG membership decides what products the user can see.

Project workspaces from the original Sprint 3 scope were retired by ADR 0018.

## Scope

- Local seed models for Access Control Groups, ACG memberships and product summaries.
- Backend services for ACG administration, product access policy and access diagnostics.
- API routes for listing, creating, editing, assigning and removing ACG members.
- Product access diagnostics for administrators.
- Frontend routes for `/admin/acgs` and `/admin/acgs/:acgId`.
- ACG administration UI for group creation, status updates, user assignment and member removal.
- Audit events for ACG creation, update, membership addition and membership removal.

## Non-goals

- Persistent database-backed ACG and product tables. These are part of the later database and migration phase.
- Product upload, asset access, search indexing and product detail pages. Those remain Sprint 5 and later.
- Real intelligence data. All seeded records are synthetic mock data.

## Access Rules

- Users must be active.
- Users must hold the relevant RBAC permission for the action.
- Product reads require `product:read`.
- Draft product visibility additionally requires product management permission.
- Product visibility requires shared ACG membership unless the user has `product:read_restricted`.
- ACG list visibility requires `acg:view`; administrators see all ACGs and product-team roles see only their relevant ACGs.
- Missing or unauthorised ACG detail reads return not-found style errors to avoid confirming inaccessible IDs.

## Acceptance Criteria

- Users can belong to many ACGs.
- Products can belong to many ACGs.
- Managers can view relevant ACGs without seeing unrelated ACG detail.
- Administrators can create and update ACGs and add or remove ACG members.
- Access diagnostics explain allow and deny outcomes.
- ACG administration changes create audit events.
- Backend and frontend tests cover ACG membership, product policy and UI workflows.

## Verification

- Backend: `uv run --directory apps/api ruff format --check src tests`, `uv run --directory apps/api ruff check src tests`, `uv run --directory apps/api mypy src` and `uv run --directory apps/api pytest` passed.
- Backend coverage: 97.04 percent total coverage.
- Frontend: `pnpm --filter @coeus/web format:check`, `pnpm --filter @coeus/web lint`, `pnpm --filter @coeus/web typecheck`, `pnpm --filter @coeus/web test`, `pnpm --filter @coeus/web build` and `pnpm --filter @coeus/web test:e2e` passed.
- Frontend coverage: 100 percent statement, line and function coverage, with 96.03 percent branch coverage.
- Security: `uv run --directory apps/api bandit -r src`, `uv run --directory apps/api pip-audit`, `uv run --project apps/api semgrep scan --config auto --error apps/api/src apps/web/src infra/docker .github` and `pnpm --filter @coeus/web audit --prod` passed.
- Infrastructure: `docker compose config` passed.

# Istari (Coeus) Documentation

Istari is the product name; Coeus is the repository and internal working name.
This index separates current guidance from acceptance contracts, decisions and
historical evidence.

## Start here

| Guide | Read it for |
| --- | --- |
| [Setup Guide](SETUP.md) | Prerequisites, installation, local startup, seed accounts and checks |
| [User Guide](USER_GUIDE.md) | Current role workspaces, screenshots and supported user journeys |
| [Roles and User Stories](ROLES_AND_USER_STORIES.md) | Roles, permissions, need-to-know groups and user stories |
| [Architecture](ARCHITECTURE.md) | Shipped system structure, data, persistence and security |
| [Architecture: Workflow](ARCHITECTURE_WORKFLOW.md) | Request lifecycle, authority flow and bounded agents |
| [Architecture: Deployment](ARCHITECTURE_DEPLOYMENT.md) | Supported local runtime and future cloud reference designs |
| [AI Agents](AI_AGENTS.md) | What each automation reads, decides, returns and may change |

## Status and authority

The [documentation maintenance guide](development/documentation-maintenance.md)
defines source-of-truth order, lifecycle labels, companion-link requirements and
the deep-audit checklist. In summary:

- current guides and runbooks describe the shipped supported boundary;
- the [current delivery tracker](MASTER_IMPLEMENTATION_PLAN.md) summarises
  implementation status, residual risk and release gates;
- the [root implementation blueprint](../coeus_spec_driven_implementation_plan.md)
  preserves original target-state history and links back to the current tracker;
- specifications, ADRs and threat models are scoped records, not automatically
  current operating instructions; and
- development stories and dated security ledgers are historical evidence.

Local synthetic/test operation is supported. Hosted and production operation
remain gated. Production requires authorised staging verification and a fresh
sealed whole-repository deep scan of the exact immutable release candidate, with
no unresolved baseline occurrence or new reportable finding.

## Current delivery and security records

| Record | Purpose |
| --- | --- |
| [Master Implementation Plan](MASTER_IMPLEMENTATION_PLAN.md) | Concise current delivery, risk and release tracker |
| [22 July remediation contract](specs/security-scan-remediation-2026-07-22.md) | Latest implemented security invariants and verification evidence |
| [ADR 0042](adr/0042-enforce-security-policy-at-final-boundaries.md) | Decision to enforce policy at final authority and parser boundaries |
| [22 July threat model](threat-model/security-scan-remediation-2026-07-22.md) | Latest scan scope, controls, residual risks and open release gates |
| [Security repair plan](security/SECURITY_REPAIR_AND_HARDENING_PLAN.md) | Sprint 17 hardening programme and historical evidence chain |

## Record collections

These indexes link every record and explain how to interpret later changes and
supersession:

- [Specifications](specs/README.md)
- [Architecture Decision Records](adr/README.md)
- [Threat Models](threat-model/README.md)

## Developer guides

| Guide | Read it for |
| --- | --- |
| [API Security and Usage](development/api-security-and-usage.md) | Authentication, errors, limits and safe automation |
| [Backend Boundaries](development/backend-boundaries.md) | Layering, transactions and backend verification |
| [Frontend Boundaries](development/frontend-boundaries.md) | React, API contracts, permissions and accessibility |
| [Customer and Analyst Context](development/customer-experience-and-analyst-context.md) | Delivered customer and analyst experience decisions |
| [Synthetic Library Assurance](development/synthetic-library-and-search-assurance.md) | Demo corpus, search assurance and evidence |
| [Documentation Maintenance](development/documentation-maintenance.md) | Authority, lifecycle, cross-linking and audit rules |

## Runbooks

| Runbook | Read it for |
| --- | --- |
| [Local Development](runbooks/local-development.md) | Daily startup, health checks and quality gates |
| [Local Multi-User Operations](runbooks/local-multi-user-operations.md) | Local onboarding, roles, teams, ACGs and account lifecycle |
| [Session Revocation](runbooks/session-revocation.md) | Revocation semantics, incident checks and recovery |
| [LiteLLM Provider Connectivity](runbooks/litellm-provider-connectivity.md) | Bedrock and Vertex routes, identity, virtual keys and verification |
| [CI/CD Pipeline](runbooks/ci-cd-pipeline.md) | GitHub Actions, required checks and security gates |
| [GitHub Branch Protection](runbooks/github-branch-protection.md) | `main` ruleset, pull requests and code-scanning results |
| [GCP Reference Deployment](runbooks/gcp-dev-deployment.md) | Future work-owned GCP migration setup and blockers |
| [Kubernetes Migration](runbooks/kubernetes-migration.md) | Evaluation topology and production readiness gates |
| [Air-Gapped Deployment](runbooks/air-gapped-deployment.md) | Offline evidence bundles and restricted environments |
| [Ticket Capacity Recovery](runbooks/ticket-capacity-recovery.md) | Dry-run diagnosis and audited PostgreSQL repairs |
| [Draft Audience Reconciliation](runbooks/draft-audience-reconciliation.md) | Backfill, zero-drift checks and cutover evidence |
| [Ticket Code Rollback](runbooks/ticket-code-rollback-reconciliation.md) | Quiesced N-1 reverse projection and forward reconciliation |
| [Coordinated Backup and Restore](runbooks/coordinated-backup-restore.md) | PostgreSQL and local-object recovery drill |

## Security operations

| Guide | Read it for |
| --- | --- |
| [Shared Resource Admission](security/shared-resource-admission.md) | Process-local Argon2, upload and parser capacity controls |
| [Workflow and Outbox Operations](security/workflow-outbox-operations.md) | Transaction, replay, repair and monitoring boundaries |
| [13 July baseline](security/SECURITY_REPAIR_BASELINE_2026-07-13.md) | Historical pre-remediation security baseline |
| [13 July closure evidence](security/SECURITY_REPAIR_CLOSURE_EVIDENCE_2026-07-13.md) | Historical Sprint 17 evidence ledger |
| [14 July remediation](security/SECURITY_REVIEW_REMEDIATION_2026-07-14.md) | Historical follow-up review evidence |
| [18 July remediation](security/SECURITY_REVIEW_REMEDIATION_2026-07-18.md) | Historical later review evidence |

## Component documentation

| Component | Documentation |
| --- | --- |
| Backend API | [API README](../apps/api/README.md) |
| API contract | [Contracts README](../packages/contracts/README.md) |
| Synthetic generators | [Mock Product Generators](../packages/mock-product-generators/README.md) |
| Synthetic test data | [Test Fixtures](../packages/test-fixtures/README.md) |
| Versioned demo corpus | [Intelligence Store Demo Assets](../demo-assets/intelligence-store/README.md) |
| Local infrastructure | [Local Infrastructure](../infra/local/README.md) |
| LiteLLM examples | [LiteLLM Routes](../infra/litellm/README.md) |
| GCP reference | [GCP Infrastructure](../infra/gcp/README.md) |

## Development history

The [Development Story](DEVELOPMENT_STORY.md) links dated archive segments and
records the latest completed work. It is a milestone log, not a source of
current runtime or release instructions.

## Screenshots and conventions

Screenshots embedded in the User Guide live in [images/](images/). They use
synthetic accounts and content. Authenticated workspaces display **MOCK DATA
ONLY**; public sign-in and access-request screens contain no app data.

- Use UK English.
- Keep every example synthetic and public-repository-safe.
- Keep the root README concise and link operational detail here.
- Update the relevant threat model with every security-sensitive change.
- Maintain at least 95 per cent line and branch coverage for backend and
  frontend application code.

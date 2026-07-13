# Istari (Coeus) Documentation

Istari is the product name; Coeus is the repository and internal working name.
This index links the guides and deeper design records.

## Guides

| Guide                                                  | Read it for                                                       |
| ------------------------------------------------------ | ----------------------------------------------------------------- |
| [Setup Guide](SETUP.md)                                | Prerequisites, installing, running locally, seed accounts, checks |
| [Architecture](ARCHITECTURE.md)                        | System structure, data and persistence, security (with diagrams)  |
| [Architecture: Workflow](ARCHITECTURE_WORKFLOW.md)     | The request journey, end-to-end sequence and AI agents            |
| [Architecture: Deployment](ARCHITECTURE_DEPLOYMENT.md) | Local runtime and the future GCP reference design                 |
| [User Guide](USER_GUIDE.md)                            | Current key-workspace screenshots and role workflows              |
| [Roles and User Stories](ROLES_AND_USER_STORIES.md)    | Roles, permissions, need-to-know groups and user stories          |
| [AI Agents](AI_AGENTS.md)                              | Exactly what each agent reads, decides and returns                |
| [API Security And Usage](development/api-security-and-usage.md) | Authentication, errors, limits and safe automation        |
| [Backend Boundaries](development/backend-boundaries.md) | Layering, transaction and verification rules                     |
| [Frontend Boundaries](development/frontend-boundaries.md) | React, API contract and accessibility rules                     |

## Repository records

| Record                                                                 | Contents                                                 |
| ---------------------------------------------------------------------- | -------------------------------------------------------- |
| [Development Story](DEVELOPMENT_STORY.md)                              | Chronological log of how the app was built               |
| [Master Implementation Plan](MASTER_IMPLEMENTATION_PLAN.md)            | Task tracking and next steps                             |
| [Specifications](specs/)                                               | One Markdown spec per feature                            |
| [Architecture Decision Records](adr/)                                  | Why the significant choices were made                    |
| [Threat Models](threat-model/)                                         | Per-feature threat models and residual risks             |
| [Security Repair Plan](security/SECURITY_REPAIR_AND_HARDENING_PLAN.md) | Current finding closure, hardening and verification work |

## Runbooks

Operational and repository-management detail lives here rather than in the root
README.

| Runbook                                                                | Read it for                                                                  |
| ---------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [Local Development](runbooks/local-development.md)                     | Day-to-day local startup, health checks and local quality gates              |
| [CI/CD Pipeline](runbooks/ci-cd-pipeline.md)                           | GitHub Actions workflows, required status checks and security gates          |
| [GitHub Branch Protection](runbooks/github-branch-protection.md)       | `main` ruleset, pull-request requirements and required code-scanning results |
| [GCP Reference Deployment](runbooks/gcp-dev-deployment.md)             | Future work-owned GCP deployment setup                                       |
| [Kubernetes Migration](runbooks/kubernetes-migration.md)               | Reusable images, evaluation topology and production readiness gates          |
| [Local Multi-User Operations](runbooks/local-multi-user-operations.md) | Local onboarding, role, team, ACG and account lifecycle                      |
| [Air-Gapped Deployment](runbooks/air-gapped-deployment.md)             | Offline evidence bundle and restricted-environment notes                     |
| [Ticket Capacity Recovery](runbooks/ticket-capacity-recovery.md)       | Dry-run diagnosis and audited PostgreSQL capacity repairs                     |
| [Draft Audience Reconciliation](runbooks/draft-audience-reconciliation.md) | Backfill, zero-drift checks and cutover evidence                          |
| [Coordinated Backup And Restore](runbooks/coordinated-backup-restore.md) | Disposable PostgreSQL and local-object recovery drill                        |

## Screenshots

The screenshots embedded in the User Guide live in [images/](images/). They use
synthetic accounts and content; authenticated workspaces display **MOCK DATA
ONLY**, while public sign-in and access-request screens contain no app data.

## Conventions

- UK English throughout.
- All data is synthetic. Do not add real intelligence content, credentials or
  operational examples.
- Keep the root README concise. Put CI/CD, branch protection, deployment and
  operations detail in runbooks, then link to it.
- Security-sensitive changes update the relevant [threat model](threat-model/).
- Backend and frontend application code each hold at least 95% line and branch
  coverage.

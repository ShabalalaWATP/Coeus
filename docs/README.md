# Istari Documentation

Start here. This index links the guides and the deeper design records.

## Guides

| Guide | Read it for |
| --- | --- |
| [Setup Guide](SETUP.md) | Prerequisites, installing, running locally, seed accounts, checks |
| [Architecture](ARCHITECTURE.md) | System structure, data and persistence, security (with diagrams) |
| [Architecture: Workflow](ARCHITECTURE_WORKFLOW.md) | The request journey, end-to-end sequence and AI agents |
| [Architecture: Deployment](ARCHITECTURE_DEPLOYMENT.md) | Local runtime and the future GCP reference design |
| [User Guide](USER_GUIDE.md) | A screenshot walkthrough of every role's workspace |
| [Roles and User Stories](ROLES_AND_USER_STORIES.md) | Roles, permissions, need-to-know groups and user stories |
| [AI Agents](AI_AGENTS.md) | Exactly what each agent reads, decides and returns |

## Project records

| Record | Contents |
| --- | --- |
| [Development Story](DEVELOPMENT_STORY.md) | Chronological log of how the app was built |
| [Master Implementation Plan](MASTER_IMPLEMENTATION_PLAN.md) | Task tracking and next steps |
| [Specifications](specs/) | One Markdown spec per feature |
| [Architecture Decision Records](adr/) | Why the significant choices were made |
| [Threat Models](threat-model/) | Per-feature threat models and residual risks |

## Runbooks

Operational and repository-management detail lives here rather than in the root
README.

| Runbook | Read it for |
| --- | --- |
| [Local Development](runbooks/local-development.md) | Day-to-day local startup, health checks and local quality gates |
| [CI/CD Pipeline](runbooks/ci-cd-pipeline.md) | GitHub Actions workflows, required status checks and security gates |
| [GitHub Branch Protection](runbooks/github-branch-protection.md) | `main` ruleset, pull-request requirements and required code-scanning results |
| [GCP Reference Deployment](runbooks/gcp-dev-deployment.md) | Future work-owned GCP deployment setup |
| [Air-Gapped Deployment](runbooks/air-gapped-deployment.md) | Offline evidence bundle and restricted-environment notes |

## Screenshots

The screenshots embedded in the User Guide live in [images/](images/). Every
screen shows synthetic data labelled **MOCK DATA ONLY**.

## Conventions

- UK English throughout.
- All data is synthetic. Do not add real intelligence content, credentials or
  operational examples.
- Keep the root README concise. Put CI/CD, branch protection, deployment and
  operations detail in runbooks, then link to it.
- Security-sensitive changes update the relevant [threat model](threat-model/).
- Backend and frontend application code each hold at least 95% line and branch
  coverage.

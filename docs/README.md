# Istari Documentation

Start here. This index links the guides and the deeper design records.

## Guides

| Guide | Read it for |
| --- | --- |
| [Setup Guide](SETUP.md) | Prerequisites, installing, running locally, seed accounts, checks |
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
| [Runbooks](runbooks/) | Local development, CI/CD, deployment, branch protection |

## Screenshots

The screenshots embedded in the User Guide live in [images/](images/). Every
screen shows synthetic data labelled **MOCK DATA ONLY**.

## Conventions

- UK English throughout.
- All data is synthetic. Do not add real intelligence content, credentials or
  operational examples.
- Security-sensitive changes update the relevant [threat model](threat-model/).
- Backend and frontend application code each hold at least 95% line and branch
  coverage.

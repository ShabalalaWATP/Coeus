# ADR 0005: Local-First Ticket Intake

## Status

Accepted.

## Context

Sprint 4 needs chatbot intake, ticket creation and timeline visibility before
database persistence and real LLM integrations exist. The implementation must
remain public-repository-safe and must not call external AI services.

## Decision

Use an in-memory ticket repository behind service interfaces. Add a deterministic
mock LLM provider and rule-based intake extraction service that returns validated
structured fields. The API exposes ticket and chat routes, while route handlers
stay thin and delegate ownership checks, completeness checks and state changes to
services.

Search is represented by an agent-run record and a transition to
`RFI_SEARCHING`; real product search remains Sprint 5.

## Consequences

- Sprint 4 can be tested locally without credentials, databases or network
  access.
- Future database repositories can replace the in-memory adapter without
  changing route contracts.
- Prompt-injection controls are testable because the mock provider does not echo
  hidden prompts or execute user-provided instructions.

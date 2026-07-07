# ADR 0015: Audit Remediation Decisions

## Status

Accepted.

## Context

A full-application audit (backend, frontend and AI agents) found broken
functionality, silent failure modes and security gaps. Several fixes required
decisions that change documented behaviour or contracts, recorded here.

## Decision

- **Provider selection is authoritative.** `COEUS_LLM_PROVIDER` decides the
  chatbot provider. An API key (environment or admin-configured) enables
  `gemini_api` but never selects it implicitly. The unimplemented
  `gemma_vertex` and `gemma_vllm` providers were removed rather than left as
  silent mock fallbacks.
- **Refusal and extraction policy applies to every provider.** Flagged
  messages receive the fixed refusal, are never sent to an external model and
  are never extracted into intake fields. Gemini failures degrade to the mock
  reply instead of failing the chat turn.
- **Intake extraction does not invent content.** Fabricated operational
  questions and success criteria were removed; the completeness checklist only
  counts what the customer provided.
- **Route overrides are same-queue.** Approving a route requires the review
  permission of the queue the ticket currently sits in. Overriding to the
  other route stays possible with a recorded reason, preserving the documented
  human-decision principle without cross-queue approval.
- **Read and write are separate ticket scopes.** A new `TICKET_WRITE_ALL`
  permission carries administrative write access; `TICKET_READ_ALL` is
  read-only.
- **Session identifiers are hashed at rest.** Deploying this invalidates
  existing sessions once, which is acceptable for a local-first system.
- **Asset tokens travel in a header.** The `X-Asset-Token` header replaces the
  query parameter so tokens stay out of logs and history; downloads happen via
  fetch and blob in the web app.
- **Delivered tickets can close.** A `CLOSED_DELIVERED` state and an
  owner-only confirm-delivery endpoint complete the lifecycle; delivery
  confirmation is a customer decision.
- **RFI search ranks the full permitted candidate set** (bounded at 500)
  rather than the first browse page, keeping the store's access policy as the
  only filter that matters.

## Consequences

Documented agent behaviour now matches the code (`docs/AI_AGENTS.md` was
updated alongside). Users must sign in again after the hashed-session deploy,
and any script that downloaded assets with a `token` query parameter must send
the header instead. The single-worker persistence constraint and ring-buffer
audit log remain, recorded in `docs/threat-model/audit-remediation.md`.

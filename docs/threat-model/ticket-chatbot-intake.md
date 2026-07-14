# Ticket And Chatbot Intake Threat Model

## Scope

Sprint 4 ticket intake, mock chat extraction, editable intake fields, attachment
metadata placeholders, agent-run records and ticket timeline.

## Assets

- Customer requirement text and structured intake fields.
- Ticket ownership and visibility rules.
- Agent-run summaries and safety flags.
- Attachment metadata, without file bytes.
- Timeline entries used by managers and downstream workflow services.

## Threats And Controls

| Threat | Control in Sprint 4 |
|---|---|
| Prompt injection asks the assistant to bypass RBAC or reveal hidden prompts. | Deterministic mock provider never executes user instructions as system policy, does not expose hidden prompts and records safety flags for suspicious text. |
| User fabricates existing product matches through chat text. | Sprint 4 records only intake/search agent runs. Product matches are not accepted from user text and real search is deferred to Sprint 5. |
| Broken object-level authorisation exposes another user's ticket. | Ticket service checks owner access and returns not-found style errors for missing or unauthorised tickets. |
| Incomplete requirements trigger downstream search too early. | Submission is blocked until required intake fields meet the completeness gate. |
| An editor or broad writer submits the request without lifecycle authority. | Submission first uses visible-ticket lookup, then requires requester ownership or `ticket:transition`. Editor and `ticket:write_all` authority alone receive a non-enumerating denial before state, timeline or audit mutation. |
| Real file upload risks malware or data leakage. | Sprint 4 supports metadata placeholders only. File bytes and object storage are out of scope. |
| Timeline tampering hides post-submission context. | Timeline entries are append-only in the service surface for Sprint 4 and include actor IDs and timestamps. |
| Requester lifecycle actions change state without audit evidence. | Cancellation and delivery confirmation restore the original ticket if audit recording fails after the proposed state update. |

## Deferred Risks

- Persistent immutability and database constraints are part of the database
  migration sprint.
- Real LLM prompt, retrieval and tool-use controls need a separate threat model
  when live providers are introduced.
- Real file upload needs malware scanning, type validation, size limits and
  object-storage access controls.

## July 2026 interface hardening

- Existing-ticket routes now wait for the exact requested record before any
  mutation controls render, preventing a delayed lookup from acting on a
  fallback ticket.
- Intake PATCH requests preserve omitted fields and represent deliberate
  clearing as explicit `null`, reducing stale sensitive metadata and accidental
  bulk erasure.

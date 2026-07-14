# Sprint 4 Spec: Ticket And Chatbot Intake

## Purpose

Add the first request-intake workflow for customer users. Sprint 4 turns free-text
chat into a draft ticket, extracts editable requirement details, records agent
runs and starts search only after the intake is complete enough.

All records remain local-first and synthetic until the database sprint. The mock
LLM provider is deterministic and must not require network access.

## Scope

- Ticket domain records with intake fields, chat transcript, attachment metadata,
  agent runs and timeline entries.
- API routes for listing visible tickets, sending chat messages, editing intake,
  adding attachment metadata, submitting intake and adding later information.
- Mock intake extraction that produces validated structured output.
- Customer request dashboard and chat workspace at `/app/requests`.
- Prompt-injection regression tests covering RBAC bypass, hidden prompt leakage
  and fabricated product claims.

## Non-goals

- Persistent database tables and migrations.
- Real LLM, vector search or product matching.
- Real file upload and asset storage.
- Analyst assignment and downstream RFA/collection workflow automation.

## Access Rules

- `chat:use` is required to send intake chat messages.
- `ticket:read_own` lets users read their own tickets.
- `ticket:read_all` lets administrators read all tickets.
- `ticket:add_information` lets a ticket owner add timeline information after
  submission.
- Submission requires requester ownership or the explicit `ticket:transition`
  permission. Editor collaboration and `ticket:write_all` do not imply this
  lifecycle capability.
- Missing or unauthorised ticket reads return not-found style errors.

## Acceptance Criteria

- Chat creates a `DRAFT_INTAKE` ticket or resumes an existing authorised ticket.
- Missing intake fields produce targeted assistant follow-up questions.
- Extracted intake fields are shown in an editable panel.
- Submit stays blocked until minimum required fields are present.
- Submission moves the ticket to `RFI_SEARCHING` and records a search agent run.
- A denied submission makes no ticket, timeline or audit mutation.
- Additional information after submission appears in the ticket timeline.
- Attachment metadata placeholders can be added without storing file bytes.
- Prompt-injection tests prove user text cannot bypass RBAC, reveal hidden
  prompts or fabricate existing product matches.

# Spec: Conversational Intake Standard And Voice Input

## Purpose

Make the customer chatbot drive the intake conversation instead of listing
missing fields. The assistant greets the customer as soon as the chat opens,
then asks one natural question per turn until every detail required for an RFI
submission is captured. Customers can also dictate messages with their voice
instead of typing.

## Scope

- A single authoritative intake standard (`INTAKE_STANDARD` in
  `apps/api/src/coeus/services/intake_standard.py`) defining, per required
  field: label, rationale and the natural elicitation question. The existing
  `REQUIRED_INTAKE_FIELDS` completeness gate is derived from it.
- Elicitation order: description, operational question, area or region,
  priority, output format, success criteria, then title.
- Mock provider replies acknowledge progress and ask exactly one question for
  the first missing field; when nothing is missing they invite the customer to
  review and submit.
- The Gemini prompt carries the same goal: acknowledge, ask one question for
  the named missing field, never several, at most two short sentences.
- The chat panel shows an assistant greeting ("What can I do for you?") before
  the first message. Read-only views keep the empty-transcript note.
- Voice input via the browser Web Speech API (`useSpeechToText` hook): a
  Dictate button appears only when the browser supports recognition, final
  transcripts append to the message box, and the customer still presses Send.

## Non-goals

- Server-side speech transcription or audio upload. If an offline deployment
  needs it, a self-hosted Whisper-class service is the follow-up.
- Changing the set of required fields, the submit gate, or extraction
  heuristics.
- LLM-driven slot filling; extraction stays deterministic and local.

## Security Notes

- Safety-flagged messages keep the fixed refusal on every provider path;
  flagged text is never sent to an external model.
- Dictation runs entirely in the browser; no audio or transcript touches the
  backend until the customer sends the message through the existing validated
  chat endpoint.

## Acceptance Criteria

- Opening a new request shows the greeting before any user message.
- Each assistant reply while intake is incomplete contains exactly one
  question, matching the standard's order.
- A complete intake produces the review-and-submit confirmation and the ticket
  becomes submittable (existing 7-field gate unchanged).
- The Dictate button is hidden when the Web Speech API is unavailable; blocked
  microphone access shows a clear hint and typing still works.

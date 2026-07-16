# Spec: Conversational Intake Standard And Voice Input

## Purpose

Make the customer chatbot drive the intake conversation instead of listing
missing fields. The assistant greets the customer as soon as the chat opens,
then asks one natural question per turn until every detail required for an RFI
submission is captured. Customers can dictate messages or explicitly start an
OpenAI Realtime speech-to-speech session when an administrator enables it.

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
- Optional realtime voice uses WebRTC and `gpt-realtime-2.1-mini`. A separate
  setting at the bottom of the admin AI panel accepts its own administrator-only
  API key, selects and enables the voice model without changing or reusing any
  text-chat provider key.
- The browser sends its SDP offer to an authenticated Coeus endpoint. Coeus
  creates the OpenAI Realtime call server-side, so the dedicated Voice API key
  is never returned to browser code.
- Stopping a voice session places the synthetic conversation transcript in the
  message editor for review and explicit submission through the existing chat
  validation and persistence path.

## Non-goals

- Durable audio recording or server-side storage of audio bytes.
- An offline speech-to-speech implementation. Browser dictation remains the
  local fallback.
- Changing the set of required fields, the submit gate, or extraction
  heuristics.
- LLM-driven slot filling; extraction stays deterministic and local.

## Security Notes

- Safety-flagged messages keep the fixed refusal on every provider path;
  flagged text is never sent to an external model.
- Dictation runs through the browser's recognition implementation; no dictated
  transcript reaches Coeus until the customer sends it.
- Realtime voice is disabled by default, requires `chat:use`, an authenticated
  session and CSRF, and is available only when an OpenAI key is configured.
- Coeus caps and validates SDP, applies provider admission, derives a stable
  privacy-preserving OpenAI safety identifier, never logs SDP or audio, and
  returns Realtime responses with `Cache-Control: no-store`.
- The SPA permits microphone access only from itself. Camera and geolocation
  remain disabled, and audio capture begins only after a user presses Start.

## Acceptance Criteria

- Opening a new request shows the greeting before any user message.
- Each assistant reply while intake is incomplete contains exactly one
  question, matching the standard's order.
- A complete intake produces the review-and-submit confirmation and the ticket
  becomes submittable (existing 7-field gate unchanged).
- The Dictate button is hidden when the Web Speech API is unavailable; blocked
  microphone access shows a clear hint and typing still works.
- The voice setting is the final section of the admin AI panel and cannot be
  enabled without an OpenAI key.
- When voice is enabled, a supported browser can start and stop a direct
  speech-to-speech session powered by the configured Realtime model.
- Older OpenAI text models are absent from the curated text catalogue, which
  contains `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna`.

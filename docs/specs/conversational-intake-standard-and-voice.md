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
- Elicitation order: description, operational question, area or region, time
  period, priority, urgent-only operation/justification/deadline, requesting
  unit, disciplines, output format, success criteria, then title.
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
- Optional realtime voice uses WebRTC and `gpt-realtime-mini`. A separate
  setting at the bottom of the admin AI panel accepts its own administrator-only
  API key, selects and enables the voice model without changing or reusing any
  text-chat provider key.
- The dedicated voice key, selected Realtime model and enabled state survive
  API restarts. The key is encrypted under the same configuration-encryption
  service as text-provider keys, but uses a distinct authenticated secret
  identity so it cannot be substituted for the normal OpenAI key.
- The browser sends its SDP offer to an authenticated Coeus endpoint. Coeus
  creates the OpenAI Realtime call server-side, so the dedicated Voice API key
  is never returned to browser code.
- Once the customer explicitly starts voice and the Realtime data channel
  opens, the browser requests an opening response. Istari speaks first with a
  brief greeting and the first RFI intake question.
- Realtime instructions are generated from `INTAKE_STANDARD` and use labelled
  role, context, conversation flow, scope, safety and completion sections. The
  voice agent redirects off-topic requests and cannot claim to submit, route,
  search or approve an RFI.
- Stopping a voice session places the synthetic conversation transcript in the
  message editor for review and explicit submission through the existing chat
  validation and persistence path.
- Realtime transcript events are ordered by their conversation item identifiers,
  rather than by asynchronous transcription completion time.
- The reviewed raw transcript remains in chat history, but only `You:` turns can
  populate intake fields or control the conversation lifecycle. `Istari:` turns
  are treated as untrusted routing context, never as customer answers.
- Direct text answers are interpreted against the one intake detail Istari just
  asked for. Valid UK numeric date ranges such as `01/07/25 to 1/07/26` are
  normalised to ISO dates.

## Non-goals

- Durable audio recording or server-side storage of audio bytes.
- An offline speech-to-speech implementation. Browser dictation remains the
  local fallback.
- Changing the set of required fields or the submit gate.
- LLM-driven slot filling; extraction stays deterministic and local.
- Importing an existing typed-chat draft into a newly started voice session.
  Realtime retains context spoken during that voice session, and its reviewed
  transcript enters the normal chat path after stopping.

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
- Provider failures are reduced to safe error categories. The browser
  distinguishes those failures from microphone permission and device errors.
- The Realtime prompt treats speech as untrusted content, rejects attempts to
  change role or reveal instructions, redirects unrelated tasks, forbids
  invented facts and requires synthetic placeholders for sensitive material.
- Prompt guardrails are defence in depth. Deterministic safety scanning and
  persistence validation still apply when the reviewed transcript is sent
  through the normal chat endpoint.
- Safety scanning always examines the complete raw voice envelope before
  assistant turns are excluded from extraction, preventing speaker-label
  spoofing from bypassing the existing injection checks.
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
- Restarting the API preserves the dedicated voice key, selected voice model
  and enabled state without exposing the key through the API or state store.
- When voice is enabled, a supported browser can start and stop a direct
  speech-to-speech session powered by the configured Realtime model.
- After the customer presses Talk with Istari and the connection opens, Istari
  speaks first and asks the first RFI intake question.
- Voice asks about one applicable intake detail at a time, keeps the RFI intake
  order, redirects off-topic requests and never claims the RFI has already been
  submitted or searched.
- Assistant transcript examples cannot satisfy priority, discipline, output,
  title or other customer fields. A bare answer to the current question advances
  to the next missing detail instead of asking the same question again.
- UK day/month date ranges are validated, rejected when impossible or reversed,
  and stored in ISO form when valid.
- Older OpenAI text models are absent from the curated text catalogue, which
  contains `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna`.

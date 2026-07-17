# ADR 0032: Server-Mediated OpenAI Realtime Voice

## Status

Accepted.

## Context

Browser dictation only turns speech into editable text. Customers also need an
optional low-latency speech-to-speech conversation powered directly by a voice
model. Standard provider keys must not enter browser state, and voice must not
silently replace the application-wide text-chat provider.

## Decision

- Treat voice as a separately enabled capability with its own curated model
  setting and dedicated administrator-entered API key. The key is independent
  from every text-chat provider key. The default model is
  `gpt-realtime-mini`.
- Persist the dedicated key as an authenticated encrypted envelope under a
  Realtime-specific identity. Persist the selected model and enabled state so
  a normal API restart does not silently disable a configured capability.
- Use browser WebRTC for audio transport. The browser sends its SDP offer to
  Coeus, and Coeus creates the OpenAI Realtime call through
  `/v1/realtime/calls` using the server-held dedicated voice key.
- Require authenticated `chat:use` permission and CSRF for session creation.
- Hold a dedicated, expiring active-session lease for each successful start,
  with global and per-user caps and authenticated release on browser teardown.
- Keep voice disabled by default and require an explicit customer action to
  start microphone capture.
- Generate structured Realtime instructions from the authoritative RFI intake
  standard. Pin Istari to intake, one-question elicitation, synthetic data,
  off-topic redirection and an explicit review-and-send completion boundary.
- Do not give the voice session tools or permission to submit, route, search or
  change a request. It may only produce a transcript for customer review.
- Keep durable ticket updates on the existing validated text-chat boundary.
  The browser exposes the captured synthetic voice transcript for review and
  explicit submission; audio is never stored by Coeus.
- Reconstruct the reviewed transcript in Realtime conversation-item order.
  Input transcription completes asynchronously and must not be ordered by
  event arrival time.
- Retain the complete reviewed transcript as the chat audit record, while
  using only requester turns as field values and lifecycle commands. Assistant
  questions may identify the field being answered but never provide its value.
- Apply the same deterministic current-question context to ordinary typed
  answers. Validate and normalise supported date formats before marking a time
  period complete.

## Consequences

The dedicated OpenAI Realtime key stays server-side, encrypted at rest, and
independent from text-provider keys and selection. Voice depends on external
network availability and OpenAI account access. Coeus must maintain tight SDP
limits, provider admission, no-store responses, audit metadata without content,
sanitised provider error categories, and a same-origin microphone permissions
policy.

A new Realtime session retains the details spoken within that voice session,
but does not inherit an existing typed-chat draft. The reviewed transcript is
merged through the normal chat path after voice stops.

The raw voice envelope is safety-scanned before any speaker filtering. This
prevents a spoofed speaker label from hiding prompt-injection content, while
keeping assistant examples out of the structured intake and downstream work.

Because WebRTC media flows directly between the browser and OpenAI after
initialisation, the application lease bounds starts and supported-client
concurrency rather than acting as a hard media proxy. Deployments must retain
provider-side usage limits and alerts. A hard per-turn spend ceiling would
require a server-proxied media architecture.

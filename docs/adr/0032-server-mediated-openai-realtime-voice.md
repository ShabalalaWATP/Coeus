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
  `gpt-realtime-2.1-mini`.
- Use browser WebRTC for audio transport. The browser sends its SDP offer to
  Coeus, and Coeus creates the OpenAI Realtime call through
  `/v1/realtime/calls` using the server-held dedicated voice key.
- Require authenticated `chat:use` permission and CSRF for session creation.
- Hold a dedicated, expiring active-session lease for each successful start,
  with global and per-user caps and authenticated release on browser teardown.
- Keep voice disabled by default and require an explicit customer action to
  start microphone capture.
- Keep durable ticket updates on the existing validated text-chat boundary.
  The browser exposes the captured synthetic voice transcript for review and
  explicit submission; audio is never stored by Coeus.

## Consequences

The dedicated OpenAI Realtime key stays server-side, and text-provider keys and
selection remain independent from voice. Voice depends on external network availability and
OpenAI account access. Coeus must maintain tight SDP limits, provider admission,
no-store responses, audit metadata without content, and a same-origin
microphone permissions policy.

Because WebRTC media flows directly between the browser and OpenAI after
initialisation, the application lease bounds starts and supported-client
concurrency rather than acting as a hard media proxy. Deployments must retain
provider-side usage limits and alerts. A hard per-turn spend ceiling would
require a server-proxied media architecture.

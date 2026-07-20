# OpenAI Realtime Voice Threat Model

## Scope And Assets

This model covers the optional browser-to-Coeus-to-OpenAI WebRTC session setup,
the administrator voice setting, microphone access, OpenAI credentials, SDP,
synthetic conversation audio and derived transcripts.

## Required Controls

| Threat                                                                            | Required control                                                                                                                                                                                                                                                                 |
| --------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| The dedicated OpenAI Realtime key reaches browser code, logs or plaintext state.  | Only an administrator can submit the separate voice key; it is not shared with text chat, and only Coeus calls OpenAI with it. Responses, errors, audit events and browser payloads never include it. At rest it uses a voice-bound AES-256-GCM envelope.                        |
| Cross-site requests create operator-funded sessions.                              | Session creation requires the authenticated session, `chat:use` and a valid CSRF token.                                                                                                                                                                                          |
| An unauthorised or cross-site caller probes the saved key through connection tests. | The test route requires `system:configure`, authenticated administrator context and CSRF. It makes one bounded server-side client-secret request, never returns the ephemeral secret and does not enable voice or mutate configuration.                                              |
| The SPA cannot read the admission token and leaks an active session.              | Expose only `X-Voice-Session-Token` through CORS and cover the allowed preflight and actual response; teardown remains authenticated and principal-bound.                                                                                                                        |
| Oversized or malformed SDP exhausts memory or reaches OpenAI.                     | Require `application/sdp`, stream with declared and received byte limits, reject NUL, invalid UTF-8 and malformed offers before provider acquisition, and bound the upstream answer.                                                                                             |
| A user spoofs another safety identity.                                            | Ignore client safety headers and derive `OpenAI-Safety-Identifier` as a domain-separated HMAC of the authenticated user ID.                                                                                                                                                      |
| One user exhausts realtime session capacity.                                      | In the documented single-process API topology, use a dedicated active-session lease with process-wide and per-principal caps, a ten-minute expiry and authenticated teardown; reserve before calling OpenAI and release failed starts.                                           |
| Audio capture or an opening response begins unexpectedly, or survives navigation. | Voice is disabled by default, the UI requires an explicit Start action before microphone capture or an opening response, pending permission can be cancelled, late streams are stopped, connections time out, and every track and peer connection is stopped on Stop or unmount. |
| Browser policy blocks the promised control or grants unrelated sensors.           | Allow `microphone=(self)` only on the SPA document; keep camera and geolocation disabled.                                                                                                                                                                                        |
| Sensitive audio or SDP is retained by Coeus.                                      | Coeus stores neither audio nor SDP, returns SDP with `Cache-Control: no-store`, and audits only actor and model metadata.                                                                                                                                                        |
| Upstream errors disclose provider details.                                        | Convert network, timeout and non-success responses to sanitised dependency categories without returning upstream bodies, request headers, exception text or credentials. The SPA surfaces only these backend-controlled messages.                                                |
| A malicious provider response consumes memory during an administrator test.       | Stream and cap the response at 64 KiB, require the expected client-secret shape and discard the returned ephemeral credential immediately.                                                                                                                                       |
| Spoken prompt injection changes Istari's role or bypasses intake safety.          | Generate labelled Realtime instructions from the authoritative intake standard, treat speech as untrusted content, reject role or prompt changes, redirect off-topic work, require synthetic placeholders and expose no submission or search tools.                              |
| A voice transcript bypasses ticket validation.                                    | Place the transcript in the existing message editor; only the normal chat endpoint can persist it. Safety-scan the complete raw envelope before parsing speaker labels.                                                                                                        |
| Assistant transcript text contaminates customer fields or controls chat state.    | Preserve the raw transcript for audit, but allow only labelled requester turns to supply field values or finish commands. Assistant questions can select answer context only. Speaker labels do not reduce raw safety scanning.                                                 |
| Asynchronous transcription events reorder questions and answers.                  | Track Realtime conversation item IDs and `previous_item_id`; render and ingest final transcripts in conversation order rather than completion-event arrival order.                                                                                                             |
| Stopping drops the final spoken turn.                                             | Stop microphone input first, commit the input buffer, briefly drain final events, parse authoritative completed events and preserve bounded deltas as a fallback before teardown.                                                                                                |
| A long voice session exhausts browser memory or exceeds chat limits.              | Bound the collected transcript and cap the resulting editor value at the existing 4,000-character chat limit.                                                                                                                                                                    |

## Residual Risks

- Audio is sent to OpenAI when a user explicitly starts voice mode. Deployments
  must use synthetic data and review provider retention and regional controls.
- Browser and device WebRTC implementations remain outside Coeus's trust
  boundary.
- Realtime prompt guardrails are probabilistic. Deterministic safety scanning
  and persistence validation begin only after the customer sends the reviewed
  transcript through normal chat, so synthetic data remains mandatory during
  the live voice session.
- The lease controls admission through the supported Coeus client, but a client
  that deliberately bypasses teardown can keep its already-issued direct
  WebRTC session until OpenAI ends it. Voice therefore remains disabled by
  default, and deployments must also configure OpenAI project usage limits and
  alerts. A server-proxied media path would be required for a hard per-turn
  spend ceiling.

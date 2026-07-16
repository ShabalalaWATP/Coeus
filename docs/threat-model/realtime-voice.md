# OpenAI Realtime Voice Threat Model

## Scope And Assets

This model covers the optional browser-to-Coeus-to-OpenAI WebRTC session setup,
the administrator voice setting, microphone access, OpenAI credentials, SDP,
synthetic conversation audio and derived transcripts.

## Required Controls

| Threat | Required control |
| --- | --- |
| The dedicated OpenAI Realtime key reaches browser code or logs. | Only an administrator can submit the separate voice key; it is not shared with text chat, and only Coeus calls OpenAI with it. Responses, errors, audit events and browser payloads never include it. |
| Cross-site requests create operator-funded sessions. | Session creation requires the authenticated session, `chat:use` and a valid CSRF token. |
| The SPA cannot read the admission token and leaks an active session. | Expose only `X-Voice-Session-Token` through CORS and cover the allowed preflight and actual response; teardown remains authenticated and principal-bound. |
| Oversized or malformed SDP exhausts memory or reaches OpenAI. | Require `application/sdp`, stream with declared and received byte limits, reject NUL, invalid UTF-8 and malformed offers before provider acquisition, and bound the upstream answer. |
| A user spoofs another safety identity. | Ignore client safety headers and derive `OpenAI-Safety-Identifier` as a domain-separated HMAC of the authenticated user ID. |
| One user exhausts realtime session capacity. | In the documented single-process API topology, use a dedicated active-session lease with process-wide and per-principal caps, a ten-minute expiry and authenticated teardown; reserve before calling OpenAI and release failed starts. |
| Audio capture begins unexpectedly or survives navigation. | Voice is disabled by default, the UI requires a Start action, pending permission can be cancelled, late streams are stopped, connections time out, and every track and peer connection is stopped on Stop or unmount. |
| Browser policy blocks the promised control or grants unrelated sensors. | Allow `microphone=(self)` only on the SPA document; keep camera and geolocation disabled. |
| Sensitive audio or SDP is retained by Coeus. | Coeus stores neither audio nor SDP, returns SDP with `Cache-Control: no-store`, and audits only actor and model metadata. |
| Upstream errors disclose provider details. | Convert network, timeout and non-success responses to a stable generic 502 response. |
| A voice transcript bypasses ticket validation. | Place the transcript in the existing message editor; only the normal chat endpoint can persist it. |
| Stopping drops the final spoken turn. | Stop microphone input first, commit the input buffer, briefly drain final events, parse authoritative completed events and preserve bounded deltas as a fallback before teardown. |
| A long voice session exhausts browser memory or exceeds chat limits. | Bound the collected transcript and cap the resulting editor value at the existing 4,000-character chat limit. |

## Residual Risks

- Audio is sent to OpenAI when a user explicitly starts voice mode. Deployments
  must use synthetic data and review provider retention and regional controls.
- Browser and device WebRTC implementations remain outside Coeus's trust
  boundary.
- The lease controls admission through the supported Coeus client, but a client
  that deliberately bypasses teardown can keep its already-issued direct
  WebRTC session until OpenAI ends it. Voice therefore remains disabled by
  default, and deployments must also configure OpenAI project usage limits and
  alerts. A server-proxied media path would be required for a hard per-turn
  spend ceiling.

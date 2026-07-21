# LiteLLM Proxy connectivity

## Status

Implemented in the current working tree on 20 July 2026.

## Goal

Allow Istari's bounded text and advisory agents to use models exposed through an
operator-approved LiteLLM Proxy, without giving a browser, user, or model authority
to choose an arbitrary network destination.

## Scope

- Add `litellm_proxy` to the existing text-provider catalogue.
- Keep the proxy base URL deployment-managed through `COEUS_LITELLM_BASE_URL`.
- Accept a LiteLLM virtual key from the existing administrator AI configuration.
- Store administrator-supplied keys only in the encrypted integration-secret store.
- Discover the key's visible model aliases through the proxy's OpenAI-compatible
  `GET /v1/models` endpoint.
- Send bounded chat-completion calls through `POST /v1/chat/completions`.
- Preserve the existing prompt, output-token, concurrency, rate, circuit-breaker,
  audit, egress-approval and deterministic-controller boundaries.
- Require a successful connection test for the chosen model before UI activation.
- Provide secret-free AWS Bedrock and GCP Vertex AI route fragments that accept
  any operator-selected LiteLLM-supported chat model or endpoint.
- Require renewable cloud workload identity, explicit production aliases and a
  LiteLLM virtual key restricted to reviewed aliases.
- Keep the secret-free route fragment in
  [`infra/litellm/model-routes.example.yaml`](../../infra/litellm/model-routes.example.yaml)
  and the operational procedure in the
  [LiteLLM Provider Connectivity Runbook](../runbooks/litellm-provider-connectivity.md).

## Non-goals

- LiteLLM does not replace the separate OpenAI Realtime voice integration.
- Istari does not administer the LiteLLM deployment or its upstream provider keys.
- Model discovery does not prove that a model obeys structured-output instructions.
  Operators remain responsible for exposing compatible chat models and running the
  application's behavioural evaluations before production approval.
- The browser cannot set or override the proxy URL.
- “Any model” does not include non-chat modalities or waive the structured-output,
  behavioural-evaluation, provider-entitlement, region or data-egress gates.
- Istari does not use cloud model wildcards or dynamically construct upstream
  provider model IDs.

## Acceptance criteria

1. LiteLLM appears as a selectable provider in the administrator panel.
2. A saved virtual key can refresh a bounded, filtered model catalogue.
3. Connection tests and live agent calls use the configured base URL and bearer key.
4. The key and provider response details are never returned to the browser or audit log.
5. Hosted startup fails when the URL is not HTTPS or is structurally unsafe.
6. Existing providers and persisted AI configuration remain backwards compatible.
7. Backend and frontend quality gates remain at or above 95 percent line and branch
   coverage.
8. An operator runbook covers AWS and GCP identity, model mapping, virtual-key
   restriction, direct verification, Istari activation, troubleshooting and
   production controls.
9. Each production alias passes a real JSON-object chat-completions test and the
   relevant Istari behavioural evaluation; catalogue visibility and the simple
   admin connection test are not treated as sufficient approval.

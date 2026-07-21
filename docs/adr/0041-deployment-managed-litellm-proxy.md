# ADR 0041: Deployment-managed LiteLLM Proxy provider

## Status

Accepted, 20 July 2026.

## Context

Istari already isolates remote model access behind one server-side gateway, encrypted
credentials, provider admission limits and deterministic application controllers.
LiteLLM Proxy exposes an OpenAI-compatible API over many upstream model providers, so
it can widen model choice without adding an SDK or a separate adapter for every vendor.

A proxy address editable by an administrator at runtime would also create a general
server-side request destination. That would materially widen the SSRF boundary and
make DNS and network policy harder to reason about.

## Decision

Add `litellm_proxy` as an OpenAI-compatible text provider. The deployment supplies the
base URL through `COEUS_LITELLM_BASE_URL`; the application appends `/v1/models` or
`/v1/chat/completions`. The administrator UI manages only the scoped LiteLLM virtual
key, visible model aliases, connection test and activation.

Hosted environments require HTTPS and reject credentials, queries, fragments, dot
segments and non-HTTP schemes in the configured URL. HTTP remains available for
local and test deployments so a developer can run LiteLLM on the local network.
Redirects remain disabled in the shared provider HTTP client.

LiteLLM receives exactly the same bounded instructions and data envelope as a direct
text provider. It receives no application tools and gains no authority to submit,
route, search, persist or approve work. Existing deterministic controllers validate
and constrain its output.

AWS Bedrock and GCP Vertex AI credentials remain in the LiteLLM deployment. The
recommended production identity is an attached or federated workload identity,
resolved through boto3's credential chain or Google Application Default Credentials.
Istari never stores those cloud credentials. Secret-free route fragments map stable
Istari aliases to operator-selected provider-prefixed model IDs.

Production routes use explicit aliases, not provider wildcards. A dedicated LiteLLM
virtual key restricts Istari to those aliases. Adding a newly available cloud model is
therefore a proxy configuration and evaluation change, followed by an Istari alias
refresh, rather than an application code change.

## Consequences

- A deployment can route Istari to any explicitly configured, approved LiteLLM
  alias compatible with chat completions and the application's bounded
  structured-output contract.
- Bedrock and Vertex AI can use renewable workload identities and any compatible
  model identifier supported by the pinned LiteLLM release without exposing cloud
  credentials to Istari.
- Changing the proxy destination requires a deployment configuration change and
  restart, which is intentional network-boundary friction.
- Model availability is not model approval. Explicit alias review, entitlement,
  regional processing, cost and behavioural evaluation remain operational gates.
- LiteLLM-side routing, logging, fallbacks and guardrails become part of the production
  trust boundary and must be configured and assessed independently.
- OpenAI Realtime voice remains a distinct integration.

# LiteLLM Provider Connectivity Runbook

## Purpose and boundary

Use this runbook to expose approved AWS Bedrock or GCP Vertex AI text models to
Istari through a deployment-managed LiteLLM Proxy. LiteLLM owns upstream cloud
identity, model routes, provider fallback, budgets and its own operational policy.
Istari owns its scoped virtual key, model-alias selection, agent prompts, egress
gates, bounded transport and deterministic controllers.

The browser and Istari administrators cannot edit the LiteLLM URL or upstream
cloud credentials. This is intentional: allowing either would widen the SSRF and
secret-management boundary.

## What “any model” means

The route template accepts any AWS Bedrock or Vertex AI model identifier that the
installed LiteLLM release supports. Istari can use an alias only when the route:

- supports OpenAI-compatible `POST /v1/chat/completions` with text messages;
- returns assistant text and, for agent paths, honours JSON-object output well
  enough to pass Istari's closed-schema validation;
- is available to the deployment identity in the configured project and region;
- has passed the application's behavioural, adversarial, cost and latency
  evaluation for its intended agent purpose.

Embedding, image, audio, rerank and realtime-only models are not compatible with
Istari's text-agent gateway. OpenAI Realtime voice remains a separate integration.
Model discovery proves only that an alias is visible to the virtual key. It does
not prove those behavioural capabilities.

Use explicit stable aliases in production. Do not expose `bedrock/*`,
`vertex_ai/*` or an all-model virtual key. Explicit aliases let operators review
provider, model release, region, data handling and spend before Istari can see a
route. Do not enable LiteLLM `drop_params`: a model that rejects Istari's
structured-output contract must fail visibly rather than silently receiving a
weakened request.

## Common setup

1. Deploy a supported LiteLLM Proxy release using LiteLLM's production guidance.
2. Merge the required entries from
   [`infra/litellm/model-routes.example.yaml`](../../infra/litellm/model-routes.example.yaml)
   into the proxy's `model_list`.
3. Supply the non-secret route values documented in
   [`infra/litellm/provider.env.example`](../../infra/litellm/provider.env.example).
4. Give the LiteLLM workload a renewable cloud identity using the platform's
   normal credential chain. Do not copy cloud secrets into Istari.
5. Start or reload LiteLLM and test each alias directly.
6. Create a dedicated LiteLLM virtual key for Istari. Restrict it to the approved
   aliases and apply appropriate token, request, concurrency, spend and expiry
   limits. Use separate keys for each environment. Never give Istari the LiteLLM
   master key.
7. Set `COEUS_LITELLM_BASE_URL` on the API deployment. Hosted deployments require
   an HTTPS URL. The standard Docker stack reaches a host-run proxy at
   `http://host.docker.internal:4000` by default.
8. In **Admin > AI provider and model**, choose **LiteLLM Proxy**, save the scoped
   virtual key, refresh aliases, select an alias and run the connection test.
9. Activate LiteLLM only after the selected alias and every configured fallback
   route have passed the production evaluation and data-egress approval.

To add another model, duplicate the matching route block, give `model_name` a
unique stable alias and set `litellm_params.model` to the new provider-prefixed
model ID. The example uses environment variables for one route per provider;
larger deployments normally keep reviewed model IDs directly in their protected
configuration or use separate environment variables for each route.

## AWS Bedrock

### Identity and access

LiteLLM uses boto3's standard credential provider chain. In AWS, attach a
dedicated IAM role to the LiteLLM workload. For local evaluation, use a short-lived
AWS IAM Identity Center or assume-role profile. Long-lived access-key pairs are a
last resort and must never be committed or entered in Istari's admin workspace.

Grant only `bedrock:InvokeModel` against the exact approved model and inference-
profile resources. Do not grant streaming, control-plane, agent, knowledge-base,
marketplace, S3 or IAM actions unless a separately approved feature proves they
are needed. Avoid `AmazonBedrockFullAccess`. Cross-Region inference profiles
need permissions for the profile and every destination model/Region, and their
data-residency implications must be approved. Some third-party models also require
marketplace entitlement or a first-use agreement before invocation succeeds.
Provision that entitlement with a separate controlled administrator identity;
do not add marketplace permissions to the LiteLLM runtime role.

Set:

```text
AWS_REGION_NAME=eu-west-2
LITELLM_BEDROCK_MODEL=bedrock/<model-id-or-inference-profile>
```

LiteLLM also supports provider-specific Bedrock routes such as
`bedrock/converse/<model-id>` when required by the selected model. Use the route
documented for that model by the installed LiteLLM release. Bedrock model IDs,
inference-profile IDs, provisioned-model ARNs and supported custom-model ARNs can
all be mapped behind a stable Istari alias where LiteLLM supports them.

### AWS preflight

- Confirm the exact model or inference profile is available in the source Region.
- Confirm the workload role can invoke it without administrator permissions.
- Confirm any marketplace terms and provider-specific first-use requirements.
- For cross-Region inference, record every possible destination Region and check
  organisation SCPs, IAM resources and data-residency policy.
- Set budgets and alarms independently in AWS and LiteLLM.

## GCP Vertex AI

### Identity and access

LiteLLM supports Google Application Default Credentials (ADC). On Google Cloud,
attach a dedicated service account to the LiteLLM workload. Outside Google Cloud,
use Workload Identity Federation. For local evaluation, use
`gcloud auth application-default login`, preferably with service-account
impersonation. Service-account key JSON is not recommended and must never be
stored in this repository or entered into Istari.

Grant the narrowest role that supports the chosen route. For production, prefer a
reviewed custom role containing `aiplatform.endpoints.predict` and only proven
quota permissions. The predefined `roles/aiplatform.user` role is a broader
evaluation starting point, not the least-privilege target. Enable the Vertex AI
API in the target project and review any additional entitlement required for
partner or open models.

Set:

```text
VERTEXAI_PROJECT=<project-id>
VERTEXAI_LOCATION=europe-west2
LITELLM_VERTEX_MODEL=vertex_ai/<model-id-or-endpoint>
```

Use a model-supported regional location unless the approved model and residency
policy explicitly permit `global`. Vertex Gemini, partner models, Model Garden
MaaS models and supported deployed endpoints can be mapped when the installed
LiteLLM release provides a compatible chat-completions adapter.

### GCP preflight

- Confirm ADC resolves to the dedicated LiteLLM identity, not a developer's
  accidental personal account.
- Confirm the Vertex AI API, model and location are available in the target
  project.
- Confirm the identity can generate content but cannot administer projects,
  service accounts or unrelated Vertex resources.
- Review partner-model terms, regional processing, logging and retention.
- Set budgets and alerts independently in GCP and LiteLLM.

## Direct proxy verification

Use a scoped Istari virtual key, not the LiteLLM master key:

```powershell
$headers = @{ Authorization = "Bearer $env:ISTARI_LITELLM_VIRTUAL_KEY" }
$models = Invoke-RestMethod `
  -Uri "$env:COEUS_LITELLM_BASE_URL/v1/models" `
  -Headers $headers
$models.data.id
```

The output should contain only approved aliases. Then test the exact alias and
structured-output shape Istari uses:

```powershell
$body = @{
  model = "istari-bedrock-primary"
  messages = @(
    @{ role = "system"; content = "Return one JSON object." }
    @{ role = "user"; content = "Return {`"status`":`"ok`"}." }
  )
  max_tokens = 32
  response_format = @{ type = "json_object" }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri "$env:COEUS_LITELLM_BASE_URL/v1/chat/completions" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

Repeat with every alias and fallback. A successful direct call is necessary but
not sufficient: the Istari admin connection test and application evaluation must
also pass.

Also prove that the virtual key cannot access an arbitrary alias or a LiteLLM
administration endpoint. For residency-sensitive deployments, do not configure
cross-provider fallbacks, a global Bedrock inference profile or a Vertex `global`
location. Availability routing is permitted only across an explicitly recorded
set with equivalent provider, model release and approved processing locations.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Alias absent after refresh | The virtual key's model allowlist, LiteLLM `model_list`, alias spelling and the bounded 200-alias Istari catalogue. |
| AWS credential error | The workload's boto3 credential chain, role trust, temporary-token expiry and `AWS_REGION_NAME`. |
| Bedrock access denied | Exact model/profile ARN permissions, destination Regions, SCPs, marketplace entitlement and first-use requirements. |
| GCP credential error | ADC source, workload identity audience/provider, service-account impersonation and mounted credential path if used. |
| Vertex permission denied | Target project, API enablement, `aiplatform.endpoints.predict`, model entitlement and location. |
| Model lists but connection test fails | Chat-completions compatibility, provider prefix, JSON-object behaviour, token parameter support and proxy logs with payload logging disabled. |
| Works locally but not hosted | HTTPS proxy URL, certificate/DNS trust, outbound firewall policy and cloud workload identity. |

## Production checklist

- Pin and patch a supported LiteLLM release and verify its image provenance.
- Use explicit aliases and a dedicated virtual key restricted to those aliases.
- Use renewable workload identity, least-privilege cloud IAM and separate duties
  for cloud, LiteLLM and Istari administrators.
- Disable or explicitly approve prompt/response logging, callbacks and retention
  at LiteLLM and every upstream provider. Keep `turn_off_message_logging: true`,
  leave detailed debug off and verify logs with synthetic canaries.
- Restrict network ingress to authorised Istari API instances and egress to the
  approved cloud endpoints. Use controlled DNS and valid TLS certificates.
- Keep LiteLLM administration endpoints on a separate private management path;
  the Istari network identity should reach only model listing and chat completion.
- Apply proxy, provider and Istari concurrency, token, rate and spend limits.
- Record provider, model release, region/profile, alias, LiteLLM config revision
  and evaluation release in the deployment approval evidence.
- Test normal replies, closed-schema agent output, prompt injection, timeout,
  throttling, fallback, malformed response, oversized response and provider
  outage before activation.
- Define key/identity rotation, rollback, incident response and model retirement
  procedures.
- Prove the workload identity is denied an unapproved model, action, project and
  Region, and that revoking the virtual key stops Istari without a code change.

## Authoritative references

- [LiteLLM AWS Bedrock provider](https://docs.litellm.ai/docs/providers/bedrock)
- [LiteLLM Vertex AI provider](https://docs.litellm.ai/docs/providers/vertex)
- [LiteLLM proxy configuration](https://docs.litellm.ai/docs/proxy/configs)
- [LiteLLM virtual keys](https://docs.litellm.ai/docs/proxy/virtual_keys)
- [AWS Bedrock model identifiers](https://docs.aws.amazon.com/bedrock/latest/userguide/foundation-models-reference.html)
- [AWS credential provider chain](https://docs.aws.amazon.com/sdkref/latest/guide/standardized-credentials.html)
- [AWS Bedrock model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)
- [AWS cross-Region inference profiles](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html)
- [Google ADC](https://cloud.google.com/docs/authentication/application-default-credentials)
- [Vertex AI supported models](https://cloud.google.com/vertex-ai/generative-ai/docs/supported-models)
- [Vertex AI generative access control](https://cloud.google.com/vertex-ai/generative-ai/docs/access-control)

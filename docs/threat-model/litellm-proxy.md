# LiteLLM Proxy threat model

## Protected assets

- Synthetic request context sent to bounded text and advisory agents.
- The LiteLLM virtual key and upstream credentials held by the proxy.
- Provider selection, model selection and agent-controller integrity.
- Service availability, provider budget and audit integrity.

## Trust boundaries

The browser talks only to Istari. Istari stores the virtual key in its encrypted
integration-secret store and calls the deployment-managed LiteLLM URL. LiteLLM and
every upstream model it can route to are external processing boundaries. A discovered
model ID is untrusted catalogue data until it passes application validation and an
administrator selects and tests it.

## Threats and controls

| Threat | Control |
| --- | --- |
| Runtime SSRF through a configurable destination | The URL is environment-managed, never accepted from an API request, structurally validated at startup and HTTPS-only when hosted. Redirects are disabled. Network egress policy remains a deployment control. |
| Key disclosure | Keys use bearer headers, never URLs. Administrator values are write-only, encrypted at rest, omitted from state responses and audit metadata, and never logged by the adapter. |
| Excessive model catalogue | IDs pass the existing character, length, family and per-source count limits before persistence. Refresh fails without replacing the current catalogue. |
| Wildcard or unintended cloud-model access | Production configuration uses explicit stable aliases and a virtual key restricted to reviewed aliases. Provider wildcards and all-model keys are prohibited. |
| Unsupported or deceptive model | Activation requires a connection test. Structured output is parsed by closed schemas and rejected or degraded by deterministic controllers. Production approval additionally requires behavioural evaluation of the selected alias and LiteLLM route. |
| Provider prompt injection or tool use | Trusted instructions are separated from request data. No tools or application credentials are exposed. Models remain advisory and cannot mutate workflow state directly. |
| Unapproved data egress | Hosted Search Planner and Routing Critic calls retain explicit provider and synthetic-classification approval gates. Intake remains local-fallback by default. |
| Cost or availability exhaustion | Existing per-principal and global admission, timeouts, output caps, response byte limits and circuit breaker apply to LiteLLM calls. LiteLLM virtual-key budgets should add a second independent limit. |
| Proxy-side retention or telemetry | The supplied route fragment disables LiteLLM message logging. Operators must keep detailed debug off and disable or approve callbacks, upstream logging and retention. Istari cannot enforce a remote proxy's storage policy. |
| DNS compromise or internal lateral movement | The URL is not runtime-editable. Production deployments must use controlled DNS, certificate validation, outbound firewall rules and a dedicated narrowly authorised virtual key. |
| Cloud credential theft | Bedrock uses an attached role or renewable federated identity through boto3; Vertex uses attached identity, Workload Identity Federation or local ADC. Long-lived cloud keys are excluded from templates, Istari and source control. |
| Region or provider drift | Each approved alias records its upstream provider, exact model or profile, source and possible destination Regions, LiteLLM configuration revision and evaluation release. Cross-Region fallback requires explicit data-residency approval. |
| Upstream privilege escalation | The LiteLLM workload identity is limited to invoking approved models. It receives no project, IAM, billing or model-administration authority. Cloud and LiteLLM administrators remain separate from Istari model selection where practicable. |

## Residual risks and production gates

- A deployment operator can deliberately configure an unsafe destination. Configuration
  review and egress firewalling remain necessary privileged controls.
- OpenAI compatibility does not guarantee identical model behaviour. Each approved
  model alias and fallback route needs deterministic contract and adversarial tests.
- Cloud model catalogues, entitlements and destination Regions change independently
  of Istari. Operators must re-review alias routes and IAM when model releases or
  inference profiles change.
- LiteLLM is another production service. Patch management, high availability, audit,
  budget policy, retention policy and incident response must cover it.

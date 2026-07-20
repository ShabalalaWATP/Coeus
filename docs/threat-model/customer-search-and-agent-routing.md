# Customer Search And Agent Routing Threat Model

## Scope

Automatic product and active-work discovery, customer resolution, JIOC agent
routing, work subscriptions, customer tracking, collection-to-analysis hand-off
and QC preflight.

## Assets And Trust Boundaries

- Intelligence Store metadata, extracted passages and embedding vectors.
- RFI, RFA and collection requirements, including hidden work existence.
- Customer decisions, route decisions, subscriptions and workflow state.
- Agent prompts, context packets, outputs, model/provider identity and audit data.
- Boundary between customer-safe projections and operational staff data.
- Boundary between probabilistic agent recommendations and deterministic state
  mutation.

## Principal Threats And Controls

### Access leakage through search

Threat: global vector retrieval, counts, citations or active-work matches reveal a
product or task that the actor cannot access.

Controls: build an authorised candidate set before ranking; reauthorise every
result at read and accept/join time; suppress hidden counts and existence; test
cross-ACG, clearance, collaboration and revocation cases with a zero-leakage gate.

### False definitive no-match

Threat: stale indexes, failed extraction, provider outage, partial coverage or a
timeout is interpreted as proof that no answer exists.

Controls: persist coverage and corpus provenance; require complete current
coverage for `definitive`; move all other zero-result cases to
`RFI_SEARCH_INCOMPLETE`; alert on incomplete and stale search rates; prevent
production provider activation until the fixed evaluation corpus passes every
release gate and the deployment is allowlisted.

### Prompt injection and untrusted intelligence content

Threat: indexed documents or customer text instruct an agent to ignore policy,
exfiltrate data or select an unauthorised route.

Controls: treat retrieved content as quoted evidence, not instructions; delimit
context; use structured output; validate routes against deterministic policy;
exclude secrets and hidden fields; record prompt template and model versions.

### Unauthorised or forged customer decisions

Threat: a collaborator or staff member accepts a product, joins work or creates
new tasking for the owner.

Controls: owner-only endpoints, CSRF validation, optimistic concurrency,
idempotency keys, fixed reason codes and atomic state-plus-audit writes.

### Agent-induced unsafe state change

Threat: malformed, low-confidence or manipulated model output changes workflow
state or silently bypasses required review.

Controls: allowlisted schema, deterministic eligibility and transition checks,
confidence/escalation thresholds, fail-closed manual review, immutable input and
output records, and no direct model access to repositories.

### Customer tracking leakage

Threat: raw timelines expose staff identities, hidden related work, operational
constraints, collection detail or internal agent reasoning.

Controls: dedicated safe projection with allowlisted stages and messages;
classification and releasability checks; separate staff endpoints; snapshot tests
for every customer-visible state.

### Subscription confused-deputy risk

Threat: joining a visible item grants broader access to its content or downstream
products.

Controls: subscription is notification/tracking intent only; it does not alter
ACLs; every canonical work and product read is independently authorised;
revocation is checked at delivery time.

### QC bypass

Threat: an agent or workflow race releases a product without current human QC.

Controls: human QC identity and decision are mandatory release preconditions;
stale version checks on approval; agent preflight cannot release; release and
audit write atomically.

## Security Verification

- object-level authorisation tests for offer, join, tracking and intervention;
- prompt-injection fixtures in product and intake text;
- stale-index, partial-index, timeout and provider-failure tests;
- concurrency and idempotency tests for accept, reject, join and consent;
- raw-timeline non-disclosure tests for customer APIs;
- route schema fuzzing and fail-closed policy tests;
- QC stale-claim and release-authority tests.

Any access leak, false definitive no-match, unauthorised state transition or QC
bypass blocks rollout.

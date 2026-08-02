# Bounded Advisory Planners Threat Model

## Status

Current for the implemented synthetic local/test boundary. Remote egress and
real-data operation remain gated as described under residual risks.

## Scope

The Intake Planner, Search Planner and shadow-only Routing Critic, including
provider transport, output admission, persisted provenance and staff/customer
projections.

## Assets And Trust Boundaries

- Extracted requirement fields and immutable routing evidence are protected
  inputs.
- Remote providers are outside the application trust boundary.
- Planner results cross back into Coeus as untrusted data.
- Deterministic controllers, authorisation services, assurance logic and state
  mutation services remain trusted policy-enforcement points.

## Threats And Controls

| Threat | Control |
| --- | --- |
| Prompt injection in requirement text instructs a planner to take actions or reveal data. | Deterministic safety scanning runs first and safety-flagged answers are not sent. Normal plans contain only bounded extracted fields. The exceptional interpretation path contains only the current active-field answer, target field and current date, never prior history or stored intake. Instructions deny authority, output is closed and the customer must confirm a valid suggestion before mutation. |
| An intake plan skips required evidence or closes the conversation. | The controller recomputes missing fields and lifecycle state. A suggestion must be a currently missing allowlisted field. The application owns all requester wording. |
| Search advice broadens access or leaks hidden product facts. | The planner sees no product corpus. Requester visibility is resolved before ranking, and result counts/evidence are projected after authorisation. Planner terms never participate in access decisions. |
| A model weakens an intake temporal constraint. | Search-planner dates remain query hints only. Intake interpretation is limited to ordered ISO dates and cannot enter `IntakeDetails` until the customer confirms application-owned summary copy. Deterministic completeness and submission checks then use the confirmed value. |
| Search expansion suppresses a real baseline match or turns absence into a definitive no-match. | The immutable base query runs independently. Supplemental candidates are unioned after it and baseline offers are preserved first. A supplemental exception is contained, exposes no provider detail, retains the authorised baseline, marks coverage partial and therefore prevents definitive absence. |
| The Routing Critic becomes a hidden second routing authority. | It runs after validation, is persisted separately and is never read by state transition or side-effect code. Tests assert route invariance across arbitrary critic results and failures. |
| Malformed or excessively large output causes resource exhaustion or parser ambiguity. | Provider timeout, output-token and response-byte ceilings apply. Schemas reject unknown fields, invalid types, excessive items and overlong/control-character text. |
| Provider calls evade deployment or egress approval. | Every remote call reserves provider admission capacity. Hosted Intake Planner egress is unavailable until classification is enforceable. Hosted Search Planner and Routing Critic egress is independently disabled by default and requires approved provider plus data-class releases at startup and call time. |
| Intake planning over-collects operational or organisational context. | The ordinary plan has an explicit four-field allowlist (`operational_question`, `area_or_region`, start and end date), bounded missing-field names and an 8 KiB total byte cap. Exceptional interpretation sends one current answer of at most 4 KiB only after deterministic extraction cannot resolve the active field. It excludes prior messages and stored intake. |
| A model invents, broadens or silently fills an intake value. | Interpretation is limited to priority and time period, must name the active target and cite an exact printable substring of the current answer. Priority suggestions use a closed enum and dates an ordered ISO range. The application asks the customer to confirm before mutation. Free text stays local. Extra fields, invalid types and malformed output are discarded; valid abstention falls back without opening the circuit. Completeness and lifecycle remain deterministic. |
| A multi-turn voice transcript leaks unrelated answers through the one-answer fallback. | Voice answers are grouped under application-recognised intake questions. Interpretation selects only the latest answer mapped to the active target and abstains locally when no target-specific answer exists. Other requester turns are neither concatenated into that prompt nor treated as its evidence. |
| One customer message causes interpretation and planning fan-out. | Interpretation reuses provider admission and the shared circuit breaker, and replaces ordinary remote planning for that turn. A message causes at most one admitted external text call. |
| Routing criticism delays a committed route or is lost in a crash gap. | Hosted shadow and active routing require relational PostgreSQL persistence and commit an identifier-only critique request atomically with the route. Composition fails closed without that transaction. The retry-safe worker resolves the exact evidence and idempotently persists one shadow record per decision. |
| Raw prompts, replies or secrets are retained in provenance. | Only normalised admitted fields, hashes, bounded counters and provider/model identifiers are stored. API keys and raw provider material are excluded. |
| Internal planner observations leak to customers. | Plans and routing criticism are staff-only projections. Customer responses expose only application-owned copy and the deterministic base search query, never planner hints. |
| Model/provider drift silently changes operational behaviour. | Prompt, policy and context-schema versions are pinned per run; invalid output falls back locally; release evaluation and provider kill switch support rollback. |
| A planner failure blocks an authorised workflow. | All three planners fail local to deterministic output. The Routing Critic is best effort after the decision and cannot fail routing. |

## Residual Risks And Required Evidence

- Valid but poor semantic suggestions can add irrelevant candidates or distract
  staff, but cannot remove baseline offers. Maintain labelled stage-specific
  evaluation sets and monitor acceptance, disagreement and retrieval metrics.
- A remote provider receives the admitted extracted context. Production use
  still requires an approved classification, redaction, provider-region and
  retention decision.
- On exceptional local/test interpretation, that context can be the raw current
  customer answer. It is bounded to one field-resolution attempt and excludes
  prior chat history. Hosted Intake Planner egress remains disabled until the
  required classification and provider release is approved.
- Normalised observations can still contain requirement-derived text. Keep them
  bounded, staff-only and subject to the ticket retention policy.
- A future proposal to give the critic veto or route authority requires a new
  specification, ADR, threat-model update and release gate. It is not an
  incremental configuration change.

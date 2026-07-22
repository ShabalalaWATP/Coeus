# Security scan remediation threat model, 2026-07-21

## Scope

Remediation of the 15 reportable findings from standard security scan
`59eb4efa-4acb-4504-b43c-bdab86f43cd7`. The target remains the supported
local-first, loopback-bound, single-writer deployment, while controls must remain
safe if the application is later hosted.

## Assets and actors

Protected assets include product bytes and metadata, request and RFI signals,
audit events, credentials, role and ACG authority, workflow state, provider
capacity and API availability. Relevant attackers are authenticated customers,
analysts or former managers; a principal whose authority changes during a
request; a malicious document; and a compromised or malfunctioning provider.

## Threats and required controls

| Threat | Required control |
| --- | --- |
| A bounded JIOC role reads global audit metadata. | Separate global audit administration from JIOC oversight permissions and projections. |
| A filtered RFI response retains a hidden positive state. | Derive all returned state, outcomes, evidence and counts from one caller-visible projection. |
| A stale manager relationship grants cross-user writes. | Require current action permission and exact current relationship at the action boundary. |
| A signed asset token outlives action permission. | Repeat live action and object authorisation during redemption. |
| A long-running mutation commits after revocation. | Include actor and material relationship freshness in the final conditional mutation. |
| A Store route skips document processing. | Make content-derived admission mandatory before object or product persistence. |
| Valid OOXML syntax bypasses byte matching. | Parse bounded relationship XML semantically and fail closed on malformed policy data. |
| Parser limits run after expensive work. | Apply incremental or preflight limits and retain isolated-worker hardening as a production option. |
| A provider buffers or drips data beyond limits. | Stream to explicit byte ceilings, enforce monotonic total deadlines and close responses on failure. |
| Deep offsets amplify database work. | Bound result windows and enforce database execution deadlines; move to keyset pagination when compatible. |

## Compatibility and abuse resistance

Controls must deny only stale authority, unsafe content or resource requests
outside the documented budget. Positive tests cover valid documents, current
permissions, current relationships, authorised audit access, visible RFI
results, normal pagination and bounded provider responses. Errors must not leak
hidden object existence, credentials, tokens, provider bodies or protected
content.

## Residual risk

- Third-party parsers remain a high-complexity attack surface until document
  processing is isolated with enforceable CPU, memory and wall-clock limits.
- A local total deadline cannot guarantee that an upstream provider stops work
  after disconnection.
- Result-window bounds mitigate offset work; keyset pagination is the durable
  large-catalogue design.
- Authority fences protect only mutations that use the guarded repository path.
  New privileged writes require variant review.
- This remediation does not replace an exhaustive deep scan, authorised staging
  testing or production capacity measurement.

## Verified remediation state, 22 July 2026

- Response projections isolate RFI visibility per caller and per ticket. A
  page-level batch contains only Store-policy-visible product identifiers;
  ticket ownership is applied independently and cannot contaminate another
  collaborator projection.
- Final mutation fences cover credential reset, analyst submission and Store
  publication. Local ticket mutation uses the consistent ticket-lock then
  authority-lock order, while PostgreSQL checks run inside the committing
  transaction.
- Download and preview token redemption repeats current action and object
  authority. Store upload rechecks the exact current actor after hostile file
  processing and removes staged or object data on rejection.
- The shared bounded HTTP transport applies absolute monotonic deadlines,
  generation-safe response interruption, identity encoding and streaming byte
  ceilings to JSON and Realtime provider calls.
- Semantic Office relationship parsing, central-directory preflight, bounded
  ZIP64 extensible metadata and incremental PDF budgets reject hostile input
  while retaining valid PDF, DOCX, PPTX, image and ZIP64 workflows.
- Full PostgreSQL-backed tests, coverage gates, static security analysis and
  dependency audits passed. Two independent final reviews found no actionable
  security or code-quality issue in the settled remediation diff.

## Follow-up scan

Later standard scan `5af0222d-05d1-4c46-a090-018aff45db2d` found eight additional
commit-time authority variants and three bounded-processing variants. Their
[controls, focused evidence and residual risk](security-scan-remediation-2026-07-22.md)
are recorded separately. Full repository gates and a fresh clean-revision scan
remain open.

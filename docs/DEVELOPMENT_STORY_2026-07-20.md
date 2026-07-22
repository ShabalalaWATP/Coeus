# Coeus Development Story, 20 July 2026

## Agent safety hardening

- Added explicit `disabled`, `shadow` and `active` JIOC routing modes. The
  evaluated v2 release now runs active for synthetic local/test use and decides
  CM versus RFA; hosted mode is explicit and disabled remains the rollback.
- Made automatic routing fail closed for missing, stale or conflicting evidence,
  unavailable team capacity, or a route unsupported by the evaluated v2 gate.
- Replaced free provider prose with closed actions and application-rendered copy,
  bounded transport and immutable safe provenance. Added authenticated outbox
  metrics, monitoring indexes and reason-required idempotent replay.
- Extended static architecture checks to keep deterministic decision modules and
  outbound provider adapters within their intended boundaries.
- Independent reviews were remediated. The final 1,339-test backend pass reached
  98.20 per cent line and 95.29 per cent branch coverage; 530 frontend tests
  reached 98.64 and 95.11 per cent, and all build/security gates passed.
- Added bounded intake and additive search planning plus a permanently shadow-only
  route critic. Adversarial tests cover authority, egress, retry and persistence;
  both full suites passed above the 95 per cent coverage gates for this milestone.

## Documentation accuracy remediation

- Reconciled guides, diagrams, ADRs, specifications and status records with active
  JIOC routing, human exception authority, lifecycle and hosted prerequisites.
  Managers are on the loop routinely and in the loop for review or intervention.
- Refreshed all 13 synthetic screenshots and added deployment-managed LiteLLM
  Proxy connectivity with bounded discovery and encrypted virtual keys.
- Contained supplemental Search Planner failures so baseline evidence survives with
  partial assurance. Final verification passed 1,452 backend tests with one skip at
  98.13/95.11 per cent line/branch coverage and 536 frontend tests at 98.63/95.05.

## LiteLLM cloud-provider onboarding

- Added secret-free AWS Bedrock and GCP Vertex AI LiteLLM route fragments using
  boto3 and Google ADC workload-identity chains rather than Istari-held cloud keys.
- Added an end-to-end operator runbook covering compatible model selection,
  explicit aliases, restricted virtual keys, IAM, regions, entitlements, direct
  tests, administrator activation, troubleshooting and production controls.
- Kept newly offered compatible cloud models configuration-driven while prohibiting
  production provider wildcards and retaining behavioural evaluation as a release
  gate.

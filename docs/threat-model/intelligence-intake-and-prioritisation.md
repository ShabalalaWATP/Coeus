# Threat Model: Intelligence Intake And Prioritisation

## Scope

Intake standard v2 (four new customer-supplied fields and the urgency
deep-dive), the conversation lifecycle, the deterministic priority ranking
that orders queues, and the scored capability team recommendation.

## Threats And Controls

| Threat | Control |
| --- | --- |
| Prompt injection lands in the new intake fields | Flagged messages skip extraction entirely for every field; regression tests assert the new fields stay blank and the conversation state does not advance. |
| Injected text reaches the external model via new fields | The Gemini prompt only ever receives extracted fields, never flagged raw text; flagged turns are answered locally with a fixed refusal. |
| Customer text games the internal queue order (stated region, unit or operation inflates priority) | Scoring is deterministic and bounded (0..1), every score carries reason tags, the submit-time snapshot is recorded as an audited agent run, managers see the breakdown, and no state changes automatically from the score. |
| Oversized or unbounded field values | Schema length caps on all four new fields (unit/operation 180, disciplines 240, justification 500); extractors cap lifted sentences. |
| Chat lifecycle abused to lock a ticket | Closing needs a complete intake plus an explicit confirmation; a closed conversation only blocks further chat, while intake editing and submission remain available to the owner. |
| Recommendation steers work to the wrong team silently | Candidates carry reasons, the suggested team remains a recommendation, and route approval (with override reason and audit) stays with the manager. |

## Open Risks

- Region, unit and operation matching is substring based on synthetic
  registries, not a validated gazetteer; a production system needs governed
  reference data and fuzzier matching.
- The priority weights are static demo constants; there is no per-deployment
  tuning or review workflow for them yet.

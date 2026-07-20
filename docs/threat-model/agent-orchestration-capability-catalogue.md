# Agent Orchestration And Capability Catalogue Threat Model

## Scope

Customer chatbot, legacy orchestrator recommendation, separate RFA/CM capability
agents, state-changing JIOC routing, the local synthetic capability catalogue,
operational availability snapshots and team-aware analyst assignment.

## Threats And Controls

| Threat | Control |
| --- | --- |
| Agent authority is mistaken for a single all-powerful role. | Capability agents and the legacy orchestrator are advisory. In explicitly allowlisted `active` mode, JIOC routing may move an eligible ticket to the assessment-assignment queue or collection-choice state. It cannot select an analyst, authorise collection execution, communicate externally, alter access/policy or release a product. Those actions remain human-controlled. |
| Bounded semantic planning is mistaken for controller authority. | Intake and Search Planners emit closed, length/count-bounded advice only. Deterministic controllers retain conversation lifecycle, required-field completion, requester wording, authorisation, structured filters, assurance and state transitions. |
| Disabled or shadow operation unexpectedly selects an operational route. | The evaluated and independently pinned release is active for supported synthetic local/test use. Hosted mode and approval are explicit. `disabled` invokes no capability agent; `shadow` persists comparison evidence. Both finish at `JIOC_REVIEW` without route side effects. Mode-specific tests and restart/redeployment into `disabled` provide rollback. |
| Mixed, negated or weak route language is treated as a confident automatic route. | Routing uses explicit evidence outcomes rather than presenting fixed keyword scores as probability. Conflicting eligibility, negation, restrictions, missing evidence and unsupported scope require clarification or JIOC Manager review. |
| Stale or absent team availability causes unsafe autonomous routing. | The immutable routing context records capability-catalogue version, candidate capacity, snapshot time and freshness. Missing, stale, unknown or wholly unavailable candidate capacity prevents auto-application. Capacity may select/escalate a team allocation; it does not silently change whether the requirement is RFA or CM. |
| The orchestrator hides which downstream agent influenced the recommendation. | Routing records separate RFA, CM and orchestrator agent runs. |
| A routing critic silently becomes a second routing authority. | The critic runs only after the deterministic decision is committed, is marked shadow-only, and has no route, state, action, disposition or tool field. Its output is never consumed by routing or downstream hand-offs. JIOC Managers see it as oversight evidence only. |
| Planner output or provenance retains injected or sensitive provider material. | Provider output is strictly admitted into normalised reason codes or bounded suggestions. Agent runs retain hashes, versions, counts and safe provider facts, never raw prompts, raw replies or credentials. Customer projections omit internal advice. |
| Clarification questions are buried in manager-only context. | Agent and manager clarification requests append customer-facing chatbot messages and a `customer_clarification_sent` timeline event. |
| Capability catalogue data is mistaken for real organisational structure. | Team names are synthetic and documentation keeps the repository public-safe. |
| Capability catalogue leaks internal routing context to customers. | `GET /routing/capability-catalogue` requires RFA or Collection review permission and the UI only appears inside manager queues. |
| A manager assigns work without recording the intended team. | Assignment accepts a team name and falls back to the agent-suggested team. |
| RFI Search reveals products outside requester ACGs. | Store and RFI Search continue to filter products before ranking, counts, offers and detail responses. |
| Site administration becomes an implicit intelligence read role. | Product detail access remains governed by RBAC, clearance and ACG intersection. Emergency admin detail and asset access use break-glass endpoints, mandatory reason capture and `product_break_glass_accessed` / `product_asset_break_glass_accessed` audit events. |

## Open Risks

- Capability matching is deterministic mock keyword scoring, not a production
  skills/capacity model. Keep JIOC routing disabled or in shadow outside synthetic
  evaluation until a representative labelled corpus, human comparison, canary and
  rollback evidence support the current policy and catalogue release.
- The shadow critic is appended after route commit. A crash can omit the
  observation but cannot alter the route. Add durable post-commit scheduling if
  critic-completeness becomes an operational service objective.

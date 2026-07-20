# Agent Orchestration And Capability Catalogue Threat Model

## Scope

Customer chatbot, legacy orchestrator recommendation, separate RFA/CM capability
agents, state-changing JIOC routing, the local synthetic capability catalogue,
operational availability snapshots and team-aware analyst assignment.

## Threats And Controls

| Threat | Control |
| --- | --- |
| Agent authority is mistaken for a single all-powerful role. | Capability agents and the legacy orchestrator are advisory. In explicitly allowlisted `active` mode, JIOC routing may move an eligible ticket to the assessment-assignment queue or collection-choice state. It cannot select an analyst, authorise collection execution, communicate externally, alter access/policy or release a product. Those actions remain human-controlled. |
| Disabled or shadow rollout unexpectedly selects an operational route. | `disabled` is the safe default, invokes no capability agent and records no agent decision. `shadow` persists comparison evidence. Both deterministically finish at `JIOC_REVIEW`, without selecting RFA/CM or creating downstream route side effects; only an evaluated and allowlisted release can use `active`. Mode-specific authority tests and an immediate return to `disabled` provide the kill switch. |
| Mixed, negated or weak route language is treated as a confident automatic route. | Routing uses explicit evidence outcomes rather than presenting fixed keyword scores as probability. Conflicting eligibility, negation, restrictions, missing evidence and unsupported scope require clarification or JIOC Manager review. |
| Stale or absent team availability causes unsafe autonomous routing. | The immutable routing context records capability-catalogue version, candidate capacity, snapshot time and freshness. Missing, stale, unknown or wholly unavailable candidate capacity prevents auto-application. Capacity may select/escalate a team allocation; it does not silently change whether the requirement is RFA or CM. |
| The orchestrator hides which downstream agent influenced the recommendation. | Routing records separate RFA, CM and orchestrator agent runs. |
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

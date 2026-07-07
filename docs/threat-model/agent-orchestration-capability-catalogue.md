# Agent Orchestration And Capability Catalogue Threat Model

## Scope

Customer chatbot, orchestrator route recommendation, separate RFA/CM capability
agents, local mock capability catalogue and team-aware analyst assignment.

## Threats And Controls

| Threat | Control |
| --- | --- |
| An agent bypasses human approval and sends work directly to analysts. | Capability checks only recommend and move tickets to manager review or clarification; analyst assignment still requires manager approval. |
| The orchestrator hides which downstream agent influenced the recommendation. | Routing records separate RFA, CM and orchestrator agent runs. |
| Clarification questions are buried in manager-only context. | Agent and manager clarification requests append customer-facing chatbot messages and a `customer_clarification_sent` timeline event. |
| Capability catalogue data is mistaken for real organisational structure. | Team names are synthetic and documentation keeps the repository public-safe. |
| Capability catalogue leaks internal routing context to customers. | `GET /routing/capability-catalogue` requires RFA or Collection review permission and the UI only appears inside manager queues. |
| A manager assigns work without recording the intended team. | Assignment accepts a team name and falls back to the agent-suggested team. |
| RFI Search reveals products outside requester ACGs. | Store and RFI Search continue to filter products before ranking, counts, offers and detail responses. |
| Site administration becomes an implicit intelligence read role. | Product detail access remains governed by RBAC, clearance and ACG intersection. Emergency admin detail and asset access use break-glass endpoints, mandatory reason capture and `product_break_glass_accessed` / `product_asset_break_glass_accessed` audit events. |

## Open Risks

- Capability matching is deterministic mock keyword scoring, not a production
  skills/capacity model.

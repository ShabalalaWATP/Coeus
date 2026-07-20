# Agent Orchestration And Capability Catalogue Spec

## Goal

Align the workflow with a customer chatbot, an orchestrator agent and separate
RFA/CM capability agents. This specification originally required every route
to be human-approved. That authority rule was superseded by
`customer-search-routing-orchestration.md` and ADR 0036: the active,
version-pinned JIOC Routing Agent may apply an eligible RFA or CM transition,
while JIOC Managers remain on the loop and handle explicit manual-review,
clarification and intervention paths.

## Status

Implemented capability-catalogue foundation. The current JIOC authority and
bounded advisory model are defined by ADRs 0036 and 0040 and their companion
specifications. Where this earlier specification conflicts with those records,
the later records take precedence.

## Scope

- Customer-facing chatbot agent records intake conversations.
- RFI Search Agent records the access-controlled existing-product search.
- Orchestrator agent records the route recommendation after reviewing RFI, RFA
  and CM outcomes.
- RFA and CM capability agents are separate services.
- Mock RFA assessment teams and CM collection teams are held in a local
  capability catalogue.
- Manager routing queues expose a read-only route-relevant view of the local
  capability catalogue.
- RFA and CM reviews include suggested team IDs and names.
- Analyst assignment accepts the selected organisational `teamId`; service-level
  compatibility can resolve the agent-suggested capability team when no
  explicit team is supplied.
- Analyst candidate data includes multiple synthetic RFA-community analysts.
- Agent or manager clarification requests are handed back to the customer as
  chatbot messages, not only timeline entries.
- Intelligence Store Manager is available as a distinct product/ACG
  administration role without blanket restricted-content read access.

## Acceptance Criteria

- Chat messages create a `customer-chatbot-agent` run.
- Submitted tickets queue and complete an `rfi-search-agent` run.
- Route checks create separate `rfa-capability-agent`, `cm-capability-agent`
  and `orchestrator-agent` runs.
- If capability checks or a manager need clarification, the ticket returns to
  `INFO_REQUIRED` with an assistant chat message containing the actual
  questions.
- RFA recommendations include a suggested assessment team.
- CM recommendations include a suggested collection capability team.
- RFA and CM manager queues display route-relevant synthetic capability teams.
- Managers select an active organisational team by `teamId` before assigning
  an analyst from that team's active membership.
- Analyst assignment candidate lists include team-aligned synthetic analysts.
- Analyst task details show the assigned team name.
- Store managers can administer Store products and ACG assignments without
  receiving unrestricted product-content visibility.
- Restricted-read administrators can use an emergency product-detail form only
  after normal access is denied, and the request must include an audit reason.
- Restricted-read administrators can request emergency asset download grants
  only after an audited product break-glass flow, and the asset grant records
  the product ID, asset ID and reason.

## Non-Goals

- Unbounded or model-authorised route approval. Bounded active JIOC routing is
  now implemented under the later version-pinned policy and deployment gates.
- Real external collection systems.
- A supported production deployment of embeddings or pgvector. Local
  PostgreSQL/pgvector retrieval mechanics are implemented and tested.
- Full multi-agent message bus or worker orchestration.

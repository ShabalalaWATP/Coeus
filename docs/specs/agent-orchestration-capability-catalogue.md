# Agent Orchestration And Capability Catalogue Spec

## Goal

Align the workflow with a customer chatbot, an orchestrator agent and separate
RFA/CM capability agents, while keeping every state-changing decision human
approved.

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
- Analyst assignment accepts a manager-entered team name and falls back to the
  agent-suggested team when omitted.
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
- Managers can enter an assignment team name when assigning an analyst.
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

- Autonomous route approval.
- Real external collection systems.
- Production embeddings or pgvector indexes.
- Full multi-agent message bus or worker orchestration.

# Roles and User Stories

Istari is role-based. Every account holds one or more roles, each role grants a
fixed set of permissions, and every account lands on a default workspace at sign
in. Permissions are enforced on the server at the object and action level, not
just in the UI, so hiding a control is a convenience, never the security boundary.

Every active account can open `/access-groups` to browse active ACGs, apply for
membership with a justification, withdraw a pending application and track its
status. ACG administration is a delegated responsibility rather than a role:
up to eight active users from any role or team may administer one ACG.
Administration permits reviewing other users' applications but does not itself
grant membership or access to protected product content.

- Role definitions: [RBAC policy](../apps/api/src/coeus/domain/rbac.py)
- Permission catalogue: [permission values](../apps/api/src/coeus/core/permissions.py)
- Access control groups (need-to-know): [ACGs](#access-control-groups-acgs)

## Roles at a glance

| Role                         | Default workspace      | Purpose                                                                                         |
| ---------------------------- | ---------------------- | ----------------------------------------------------------------------------------------------- |
| Administrator                | `/admin/overview`      | Governance: access, AI, search, voice, ACGs, audit and analytics                                |
| Customer                     | `/app/requests`        | Raise and track intelligence requests                                                           |
| JIOC Team Member             | `/jioc/queue`          | Resolve routing exceptions and independently adjudicate referred re-analysis disputes           |
| JIOC Manager                 | `/jioc/oversight`      | On-loop oversight, audited intervention and routing-exception support                            |
| RFA Manager                  | `/rfa/queue`           | Lead the RFA team: assign analysts, approve analyst work, manage the team                       |
| RFA Team Member              | `/rfa/products`        | Maintain entitled RFA product metadata and assets                                                |
| CM Manager                   | `/collection/queue`    | Lead the CM team: assign analysts, approve analyst work, manage the team                        |
| CM Team Member               | `/collection/products` | Maintain entitled Collection product metadata and assets                                         |
| Analyst                      | `/analyst/workbench`   | Produce draft products against assigned tasks                                                   |
| Quality Control (QC) Manager | `/qc/queue`            | Quality-assure products and perform the final release                                           |
| Intelligence Store Manager   | `/store`               | Curate the catalogue and register controlled products without blanket content access             |

Legacy role names ("Request for Assessment Manager", "Collection Manager",
"Collection Team Member", "Intelligence Analyst", "User") still decode from
persisted data and are accepted by the admin API, normalising to the names
above.

A separate account state exists before a role is granted: a **pending registrant** who has
requested access from the sign-in page and is awaiting administrator approval.

## What each role can do

The tables below summarise the meaningful capabilities. "Products" always means
products the user is entitled to see through their access control groups.

### Administrator

Holds every permission. In practice the admin governs rather than operates:
approves or rejects access requests, manages users, roles, clearance and account
status, configures text-chat AI, search embeddings and Realtime voice, manages
ACGs, and reads the audit log and global analytics.

### Customer

- Create requests and drive the chat intake.
- Track their own requests on a dashboard and view the request journey.
- Tag colleagues on a request as editors or viewers.
- Accept or reject RFI product offers.
- Search the Intelligence Store and download products they are entitled to.
- Submit feedback. There is no customer analytics dashboard.
- Confirm whether a released product meets the requirement or request
  re-analysis with a reason and optional unmet criteria.
- Cannot see other customers' requests, route tickets, or produce products.
- Apply for active ACGs and track or withdraw pending applications.

### JIOC Team Member

- Review requests that the active JIOC Agent cannot safely route automatically,
  with the capability evidence and routing recommendation beside them.
- Approve or override CM/RFA routing with a reason, query the requester, reject a
  route, and review or link similar open requests.
- Independently adjudicate a customer re-analysis dispute referred by the
  responsible RFA or Collection manager.
- Does not assign analysts, edit analyst work or access protected products.

### JIOC Manager

- Remain on the loop through JIOC Oversight rather than approving every routine
  decision made by the active JIOC Agent.
- Monitor workflow and route totals, active area teams, analyst capacity,
  bounded task ownership and shadow Routing Critic evidence.
- Use audited controls to hold or resume eligible work, or send an eligible
  automated route to the JIOC exception queue.
- Can perform JIOC Team Member exception and re-analysis decisions when needed,
  subject to the same recorded-reason and separation-of-duties controls.
- View aggregate platform analytics. This does not grant access to protected
  workflow or product content.
- Does not gain access to analyst notes, draft bodies or protected product
  content through oversight.

### RFA Manager / CM Manager

- Lead their area: select any active team in RFA or CM respectively, then assign
  one to five active analysts from that selected team and define work packages.
- Approve or return analyst work before it reaches Quality Control.
- Review a customer's post-release re-analysis request: agree and start a new
  analysis cycle, or refer a disagreement to an independent JIOC human.
- Manage the team roster and calendar, and view team analytics.
- Do not release products: Quality Control performs the final release.
- A manager sees and acts across their route area; the selected team remains the
  authoritative owner for candidate membership and availability.

### RFA / CM Team Member

- Maintain metadata and assets for entitled team products.
- Cannot register a new existing Store product; that upload permission belongs
  to the corresponding manager and Intelligence Store Manager roles.
- Read and search entitled products.
- Do not approve routes, assign analysts or release products.

### Analyst

- See only tasks assigned to them; a task may be shared by up to five analysts.
- Complete work packages, keep working notes, link supporting products and draft
  the product.
- Submit the draft to the team manager for approval (QC-requested rework goes
  straight back to QC).
- Cannot approve their own work or release it.

### Quality Control Manager

- See safe summaries in the shared QC queue, claim one review atomically and
  release the claim deliberately when a hand-off is needed.
- See full product detail and linked drafts only while assigned to that review.
- Review submitted drafts and approve or reject them.
- On approval, ingest the product and perform the final release to the
  customer; for an analysed collect, forward the ticket to RFA assignment with
  the collect linked instead of releasing it.
- Cannot approve a draft they authored (separation of duties is enforced).

### Intelligence Store Manager

- Browse catalogue metadata without first entering a search criterion.
- Register draft or published existing products for either RFA or Collection,
  including their metadata, asset records and product ACG assignments.
- Add or remove direct ACG membership as a distinct governance action.
- Manage Store operations without receiving unrestricted report-content access.
- Read product contents only when their account has at least one matching ACG,
  while administrators must use an explicitly audited break-glass endpoint for
  support access outside their ACGs.

## User stories

### Customer

- As a customer, I want to describe what I need in plain language so that I do
  not have to learn a form or the workflow.
- As a customer, I want one clear follow-up question at a time so that Istari
  can resolve missing detail without exposing an internal checklist.
- As a customer, I want to be offered existing products first so that I get an
  answer immediately when one already exists.
- As a customer, I want to see where my request is in the pipeline so that I know
  what happens next without asking anyone.
- As a customer, I want to tag a colleague as a viewer or editor so that they can
  follow or help refine the request.
- As a customer, I want a dashboard of my open requests and a link plus a
  notification when a product is released so that I never miss a delivery.
- As a customer, I want to confirm whether a released product meets my need and
  request reasoned re-analysis when it does not.

### JIOC Team Member

- As a JIOC team member, I want the active JIOC Agent to route clear eligible
  requests so that I can focus on ambiguous, restricted or unsafe exceptions.
- As a JIOC team member, I want to query or reject a route with a recorded
  reason so that the decision trail is auditable.
- As a JIOC team member, I want to override the recommendation with a
  justification so that I stay in control when the agent is wrong.
- As an independent JIOC reviewer, I want to adjudicate a referred re-analysis
  disagreement so that neither the requester nor production team has unilateral
  authority.

### JIOC Manager

- As a JIOC manager, I want an on-loop view of routing and production outcomes
  so that routine automation remains observable without requiring my approval.
- As a JIOC manager, I want audited hold, resume and send-to-review controls so
  that I can intervene within explicit boundaries when evidence or risk changes.

### RFA / Collection Manager

- As an RFA or Collection manager, I want to assign one or more analysts with
  the team availability in front of me so that production starts with people
  who are actually free.
- As an RFA or Collection manager, I want to approve or return my analysts'
  work with a reason so that nothing reaches Quality Control unreviewed.
- As an RFA or Collection manager, I want to manage my team's roster and
  calendar so that ownership of my analysts is explicit.
- As an RFA or Collection manager, I want to review a customer's reasoned
  re-analysis request and refer disagreements for independent adjudication.

### Analyst

- As an analyst, I want to see only my assigned tasks so that my workbench is not
  cluttered with everyone else's work.
- As an analyst, I want work packages, notes and linked products in one place so
  that I can produce the draft efficiently.
- As an analyst, I want to submit for manager approval in one action once my
  checklist is complete so that hand-off is unambiguous.

### Quality Control Manager

- As a QC manager, I want to claim one queued review before seeing its detail so
  that review ownership and need-to-know access are explicit.
- As a QC manager, I want competing claims to fail safely and released claims to
  return to the shared queue so that hand-offs cannot create two reviewers.
- As a QC manager, I want to review a draft against quality and releasability so
  that only sound products progress.
- As a QC manager, I want to be blocked from approving my own draft so that
  separation of duties is guaranteed.
- As a QC manager, I want approval to ingest and release the product to the
  customer so that the final controlled hand-off is automatic and recorded.

### Administrator

- As an administrator, I want to approve or reject access requests with a reason
  so that only vetted people get accounts.
- As an administrator, I want to choose the AI model the agents use, with tiers
  and descriptions, so that I can balance latency, cost and capability.
- As an administrator, I want separate search-embedding and Realtime voice
  controls so each external data path has its own key, test and enablement gate.
- As an administrator, I want to see who last changed the model and when so that
  the change is accountable.
- As an administrator, I want realistic need-to-know groups so that product
  visibility reflects how teams are actually organised.
- As an administrator, I want to delegate each ACG to up to eight active users
  from any role so access decisions sit with appropriate subject experts.

### Delegated ACG administrator

- As an ACG administrator, I want to review justified applications only for my
  groups so I can make bounded need-to-know decisions.
- As an ACG administrator, I want administration to remain separate from my own
  membership so governance authority does not silently grant content access.
- As an ACG administrator, I must not decide my own application so another
  authorised person always confirms my access.

### Intelligence Store Manager

- As an Intelligence Store Manager, I want to register controlled product
  metadata, assets and ACG labels for either area so that the Store stays useful
  without granting me blanket access to report contents.

### Pending registrant

- As a prospective user, I want to request access from the sign-in page so that I
  can be onboarded without a side channel.
- As a prospective user, I want a generic confirmation so that the system does
  not reveal whether an account already exists.

## Access control groups (ACGs)

Need-to-know is enforced by access control groups. A product is visible to a user
only if they are in one of the product's ACGs (and meet its clearance and status
rules). Istari seeds 43 groups:

- Three original workflow groups (Alpha Regional, Bravo Collection, Charlie
  Assessment).
- Forty themed groups formed from eight regions (European, African, Middle
  Eastern, Asia-Pacific, North American, South American, Arctic, Maritime)
  crossed with five disciplines (Cyber, HUMINT, SIGINT, GEOINT, OSINT), for
  example "European Cyber" (`ACG-EU-CYBER`) or "Maritime GEOINT".

Every user can request membership from the Access Groups workspace. Delegated
ACG administrators decide applications for their groups, while platform
administrators manage group definitions and delegated administrator rosters.
See the [User Guide](USER_GUIDE.md#access-groups) for the workflow and
`apps/api/src/coeus/repositories/access.py` for the seed data.

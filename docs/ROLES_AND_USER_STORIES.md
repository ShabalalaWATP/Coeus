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

- Role definitions: `apps/api/src/coeus/domain/rbac.py`
- Permission catalogue: `apps/api/src/coeus/core/permissions.py`
- Access control groups (need-to-know): [ACGs](#access-control-groups-acgs)

## Roles at a glance

| Role                         | Default workspace      | Purpose                                                                                         |
| ---------------------------- | ---------------------- | ----------------------------------------------------------------------------------------------- |
| Administrator                | `/admin/overview`      | Governance: access requests, model selection, ACGs, audit, analytics                            |
| Customer                     | `/app/requests`        | Raise and track intelligence requests                                                           |
| JIOC Team Member             | `/jioc/queue`          | Decide whether a progressed request needs collection (route to CM) or assessment (route to RFA) |
| RFA Manager                  | `/rfa/queue`           | Lead the RFA team: assign analysts, approve analyst work, manage the team                       |
| RFA Team Member              | `/rfa/products`        | Contribute assessment products                                                                  |
| CM Manager                   | `/collection/queue`    | Lead the CM team: assign analysts, approve analyst work, manage the team                        |
| CM Team Member               | `/collection/products` | Contribute collection products                                                                  |
| Analyst                      | `/analyst/workbench`   | Produce draft products against assigned tasks                                                   |
| Quality Control (QC) Manager | `/qc/queue`            | Quality-assure products and perform the final release                                           |
| Intelligence Store Manager   | `/store`               | Administer product metadata, assets and ACG assignment without blanket content access           |

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
status, chooses the AI provider and model, manages ACG membership, and reads the
audit log and global analytics.

### User (Customer)

- Create requests and drive the chat intake.
- Track their own requests on a dashboard and view the request journey.
- Tag colleagues on a request as editors or viewers.
- Accept or reject RFI product offers.
- Search the Intelligence Store and download products they are entitled to.
- Submit feedback and view their own analytics.
- Cannot see other customers' requests, route tickets, or produce products.
- Apply for active ACGs and track or withdraw pending applications.

### JIOC Team Member

- Review progressed requests with the capability recommendation beside them.
- Decide whether collection is required: yes routes to the CM team, no routes
  to the RFA team; may query the requester instead.
- Use JIOC Oversight to monitor workflow-state totals, route totals, active area
  teams, analyst capacity and bounded task ownership across the whole process.
- Does not assign analysts, edit analyst work or access protected products.

### RFA Manager / CM Manager

- Lead their area: select any active team in RFA or CM respectively, then assign
  one to five active analysts from that selected team and define work packages.
- Approve or return analyst work before it reaches Quality Control.
- Manage the team roster and calendar, and view team analytics.
- Do not release products: Quality Control performs the final release.
- A manager sees and acts across their route area; the selected team remains the
  authoritative owner for candidate membership and availability.

### RFA / CM Team Member

- Contribute products for their team and manage product metadata and assets.
- Read and search entitled products.
- Do not approve routes, assign analysts or release products.

### Intelligence Analyst

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

- Administer product metadata, assets and product ACG assignment.
- Manage store operations without receiving unrestricted report-content access.
- Read product contents only when their account has at least one matching ACG,
  while administrators must use an explicitly audited break-glass endpoint for
  support access outside their ACGs.

## User stories

### Customer

- As a customer, I want to describe what I need in plain language so that I do
  not have to learn a form or the workflow.
- As a customer, I want to be told exactly which details are still missing so
  that my request is not rejected later for being incomplete.
- As a customer, I want to be offered existing products first so that I get an
  answer immediately when one already exists.
- As a customer, I want to see where my request is in the pipeline so that I know
  what happens next without asking anyone.
- As a customer, I want to tag a colleague as a viewer or editor so that they can
  follow or help refine the request.
- As a customer, I want a dashboard of my open requests and a link plus a
  notification when a product is released so that I never miss a delivery.

### JIOC Team Member

- As a JIOC team member, I want capability agents and the orchestrator to
  assess feasibility and recommend a route so that I can decide quickly with
  the reasoning in front of me.
- As a JIOC team member, I want to query or reject a route with a recorded
  reason so that the decision trail is auditable.
- As a JIOC team member, I want to override the recommendation with a
  justification so that I stay in control when the agent is wrong.

### RFA / Collection Manager

- As an RFA or Collection manager, I want to assign one or more analysts with
  the team availability in front of me so that production starts with people
  who are actually free.
- As an RFA or Collection manager, I want to approve or return my analysts'
  work with a reason so that nothing reaches Quality Control unreviewed.
- As an RFA or Collection manager, I want to manage my team's roster and
  calendar so that ownership of my analysts is explicit.

### Intelligence Analyst

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

- As an Intelligence Store Manager, I want to administer product metadata,
  assets and ACG labels so that the store stays useful without granting me
  blanket access to report contents.

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

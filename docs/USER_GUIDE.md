# Istari User Guide

This guide walks through Istari by role, with screenshots of each workspace. All
data shown is synthetic and authenticated workspaces are labelled **MOCK DATA
ONLY**. Desktop is the supported experience. Mobile layouts have not been
designed or validated and must not be presented as supported.

For how to run the app locally see the [Setup Guide](SETUP.md). For the roles and
their permissions see [Roles and User Stories](ROLES_AND_USER_STORIES.md). For
how the agents work see [AI Agents](AI_AGENTS.md).

## Contents

- [Signing in](#signing-in)
- [Requesting access](#requesting-access)
- [The request journey](#the-request-journey)
- [Customer](#customer)
- [Intelligence Store](#intelligence-store)
- [JIOC team members](#jioc-team-members)
- [RFA and Collection managers](#rfa-and-collection-managers)
- [Intelligence analyst](#intelligence-analyst)
- [Quality control](#quality-control)
- [My Team](#my-team)
- [Administrator](#administrator)
- [Users and account lifecycle](#users-and-account-lifecycle)

---

## Signing in

The sign-in page doubles as a splash that introduces the product. Accounts are
assigned; there is no open self-registration, only a request-access flow.

![Istari sign-in and splash page](images/01-splash-login.png)

Local seed accounts (see the [Setup Guide](SETUP.md#seed-accounts)) all use the
mock credential `CoeusLocal1!`.

## Requesting access

A prospective user switches to **Request access** and submits their details. The
request is queued for an administrator to approve; the response is deliberately
generic so the page never reveals whether an account already exists.

![Request access form](images/02-request-access.png)

## The request journey

At any time a customer can open **Request journey** to see the seven stages a
request moves through and where theirs currently sits. The popup is transient and
opens automatically the first time a request is submitted.

![Request journey popup](images/05-request-journey.png)

Each stage is handled by a person supported by an Istari agent; the stages map
directly onto the [agents](AI_AGENTS.md#agents-at-a-glance).

---

## Customer

Customers get two focused screens. The **dashboard** shows status metrics and a
list of their requests, with one action to open a new request.

![Customer request dashboard](images/03-customer-dashboard.png)

Opening a request shows the **chat-first workspace**. On the left the intake
assistant captures the requirement conversationally; on the right a live
checklist shows which core and priority-dependent details have been captured,
with a manual edit panel and product offers below.

![Customer request workspace with intake assistant and checklist](images/04-request-workspace.png)

From here a customer can:

- Chat with the intake assistant until every detail displayed in the checklist
  has been captured.
- Edit any detail directly in "Edit details manually".
- Tag colleagues as editors or viewers.
- Submit the request, then accept or reject any existing-product offers.
- If no existing product matches, choose **Yes, task as new request** to continue
  into route assessment, or **No, cancel request** to stop the ticket with a
  recorded reason.

After submission, Istari also checks open requests for likely overlap. If a
visible similar request is already in progress, the workspace shows its
reference, title, score and reasons with **Join as viewer** and **Continue
request** actions. If overlap exists but the customer has no need-to-know for
the matching ticket, the workspace shows only a neutral note that the assessing
team will check for overlapping work.

## Intelligence Store

The Intelligence Store is a controlled search service. The collapsible
**Search and filters** panel supports full text, product type, region, tag,
source type and coverage dates; results can be sorted by relevance, title or
newest coverage. Filters run **after** access control and classification checks,
so a customer only ever sees products they are entitled to.

![Intelligence Store search and results](images/06-intelligence-store.png)

Each result carries rich metadata: reference, owning team, region,
classification, coverage window, tags and format. RFA managers, Collection
managers and Intelligence Store Managers can administer store metadata and
assets. Viewing or downloading product content still depends on ACG membership
and clearance.

---

## JIOC team members

Progressed requests land in the JIOC queue. Selecting a ticket and running
**capability checks** invokes the RFA and CM capability agents plus the
orchestrator; their advice appears as agent-badged cards alongside a
recommended route. The JIOC member decides whether collection is required
(route to CM) or not (route to RFA), can approve against the recommendation
with a written override reason, review and link similar open requests, or
query/reject the route with a recorded reason. When a request is routed to
CM, the customer is asked in their workspace whether they want the **raw
collect only** or the **collect plus an RFA analysis**.

![JIOC routing queue with agent recommendations](images/07-rfa-queue.png)

## RFA and Collection managers

Managers work their own team's queue and lead their team:

- **Assign one to five analysts** with a team name and work packages once
  JIOC approves the route; the panel shows how many team members are free
  today from the team calendar and live assignments.
- **Approve or return analyst work**: submitted drafts stop at manager
  approval, where the manager forwards them to Quality Control or returns
  them with a rework reason. A manager cannot approve work they drafted.
- **Manage the team** on the My Team page: roster, member profiles and the
  availability calendar.

## Intelligence analyst

The analyst workbench lists only the tasks assigned to the signed-in analyst;
a task can be shared by several analysts. Selecting a task shows its context,
work packages, and progressive-disclosure sections for working notes and
linked products, with the draft form and **Submit for manager approval**
action below (QC-requested rework resubmits straight to QC).

![Analyst workbench](images/08-analyst-workbench.png)

## Quality control

The QC manager reviews submitted drafts and approves or rejects them. Approval
now performs the final release: the product is published, disseminated to the
requester with a notification and a recorded email, and a feedback request is
raised. For a collect the customer asked to have analysed, approval instead
forwards the ticket to RFA assignment with the collect linked (the collect
itself is never released). A QC manager cannot approve a draft they authored.

![Quality control queue](images/09-qc-queue.png)

## My Team

Everyone on a team gets the **My Team** page: the roster with each member's
title and specialisms, a two-week availability calendar and today's
availability tile. Members log their own availability; managers can log for
anyone on their team, and add or remove members. Every user edits their own
profile (title, specialisms, bio) at the bottom of the page.

---

## Administrator

The Admin workspace is the governance control plane. It shows service status,
pending **access requests** to approve or reject with a reason, and the AI model
catalogue. The left navigation exposes operational workspaces, analytics, Users,
ACGs and the audit log according to the administrator's permissions.

![Administrator overview](images/10-admin-overview.png)

### Choosing the AI model

The **AI model** panel groups models by provider. Gemini, OpenAI, Vertex AI and
Bedrock can each accept a write-only runtime key, test the connection and retain
their own selected model. Activating a provider is a separate warned action that
changes the provider for every user. Runtime keys are not returned to the browser
or persisted and disappear when the API restarts; model choices are persisted.

![Admin AI model catalogue](images/12-admin-ai-model.png)

### Access control groups

The **ACGs** workspace manages the 43 seeded need-to-know groups and their
membership. Groups are themed by region and discipline (for example "European
Cyber", "Maritime GEOINT") so product visibility reflects how teams are actually
organised.

![Access control groups](images/11-admin-acgs.png)

### Users and account lifecycle

The **Users** workspace searches and filters accounts. An administrator can
assign roles, change clearance, activate or deactivate an account, and issue a
temporary credential that is displayed once. The signed-in administrator cannot
change their own protected fields. Role assignment, team membership and ACG
membership are separate controls and should all follow least privilege.

![Administrator user management](images/13-admin-users.png)

For the full local onboarding and offboarding sequence, including its
single-writer and non-production boundaries, see [Local Multi-User
Operations](runbooks/local-multi-user-operations.md).

# Istari User Guide

This guide walks through Istari by role, with screenshots of each workspace. All
data shown is synthetic and labelled **MOCK DATA ONLY**. Desktop is the primary
experience; the layout is responsive down to mobile widths.

For how to run the app locally see the [Setup Guide](SETUP.md). For the roles and
their permissions see [Roles and User Stories](ROLES_AND_USER_STORIES.md). For
how the agents work see [AI Agents](AI_AGENTS.md).

## Contents

- [Signing in](#signing-in)
- [Requesting access](#requesting-access)
- [The request journey](#the-request-journey)
- [Customer](#customer)
- [Intelligence Store](#intelligence-store)
- [RFA and Collection managers](#rfa-and-collection-managers)
- [Intelligence analyst](#intelligence-analyst)
- [Quality control](#quality-control)
- [Administrator](#administrator)

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
checklist shows how many of the seven required details have been captured, with a
manual edit panel and product offers below.

![Customer request workspace with intake assistant and checklist](images/04-request-workspace.png)

From here a customer can:

- Chat with the intake assistant until the checklist reads "7 of 7 captured".
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

## RFA and Collection managers

RFA and Collection managers work route-specific queues. Selecting a ticket and
running **capability checks** invokes the RFA and CM capability agents plus the
orchestrator; their advice appears as agent-badged cards alongside a recommended
route.

![RFA manager queue with agent recommendations](images/07-rfa-queue.png)

A manager can:

- **Approve** the recommended route, or approve the other route with a written
  override reason.
- **Review similar open requests** before deciding the route and link related
  work so both ticket timelines show the relationship.
- **Query or reject** the route (the form is tucked behind a disclosure to keep
  the screen focused).
- **Assign an analyst** with a team name and work packages once a route is
  approved.
- **Release** a QC-approved product to the customer from the Final Release panel,
  which publishes the product, links it on the customer's dashboard, sends a
  notification and records the email in the local outbox.

Collection managers get the same screen scoped to the collection route.

## Intelligence analyst

The analyst workbench lists only the tasks assigned to the signed-in analyst.
Selecting a task shows its context, work packages, and progressive-disclosure
sections for working notes and linked products, with the draft form and
**Submit to QC** action below.

![Analyst workbench](images/08-analyst-workbench.png)

## Quality control

The QC manager reviews submitted drafts and approves or rejects them. Approval
ingests the product as an unpublished draft and moves the ticket to manager
release; a QC manager cannot approve a draft they authored.

![Quality control queue](images/09-qc-queue.png)

---

## Administrator

The Admin workspace is the governance control plane. It shows service status,
pending **access requests** to approve or reject with a reason, and the AI model
catalogue. The left navigation exposes every team queue, analytics, ACGs and the
audit log.

![Administrator overview](images/10-admin-overview.png)

### Choosing the AI model

The **AI model** panel presents each available model as a selectable card with a
tier (Sovereign, Fast, Advanced, or Custom for anything unrecognised) and a
description. The active model is badged, and the panel records who last changed
it and when. Entering a Gemini API key enables Gemini-backed assistant replies
for every user in the current API process, but the key is write-only and not
persisted; model choice is persisted.

![Admin AI model catalogue](images/12-admin-ai-model.png)

### Access control groups

The **ACGs** workspace manages the 43 seeded need-to-know groups and their
membership. Groups are themed by region and discipline (for example "European
Cyber", "Maritime GEOINT") so product visibility reflects how teams are actually
organised.

![Access control groups](images/11-admin-acgs.png)

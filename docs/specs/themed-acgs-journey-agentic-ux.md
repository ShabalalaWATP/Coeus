# Themed ACGs, request journey and agentic UX polish

Status: implemented (2026-07-06)

## Goal

Make the mock deployment feel like a realistic, modern, AI-first tasking
system: seed a believable set of need-to-know groups, show requesters where
their request goes, keep every role screen focused on its primary action and
give administrators a proper model catalogue for the Gemini selection.

## Scope

### 1. Themed access control groups (backend seed data)

- Seed 40 themed ACGs as the cross product of eight regions (European,
  African, Middle Eastern, Asia-Pacific, North American, South American,
  Arctic, Maritime) and five disciplines (Cyber, HUMINT, SIGINT, GEOINT,
  OSINT), for example `European Cyber` (`ACG-EU-CYBER`).
- The three original workflow ACGs remain, giving 43 in total.
- The admin belongs to every themed group; a small set of themed
  memberships is seeded for the workflow roles so store need-to-know
  filtering demonstrates realistic overlap (for example the customer and
  analyst share `European Cyber` but only managers hold `Middle Eastern
  HUMINT`).
- No access-control logic changes: membership checks, clearance and
  audit behave exactly as before.

### 2. Request journey popup (customer)

- A transient dialog (`RequestJourney`) maps every ticket state onto seven
  plain-language stages: describe, RFI search, route review, analyst
  production, QC, manager release, delivered.
- It opens automatically once when a requester submits their ticket and on
  demand from a "Request journey" button beside the status pill.
- It closes on Escape, overlay click or the close button and holds no
  server state. Unknown states fall back to the first stage;
  `CLOSED_EXISTING_PRODUCT_ACCEPTED` explains that an existing product
  satisfied the request.

### 3. Agentic, simplified role screens

- The intake chat is presented as the customer chatbot with a typing
  indicator while a message is in flight.
- Agent chips (`Routing agent`, `Capability agent`, `RFI search agent`)
  label machine-generated recommendation cards so human actions and agent
  advice are visually distinct.
- Analyst task detail collapses working notes and linked products behind
  `<details>` disclosures; work packages, the draft form and QC submission
  stay primary.
- Manager queues collapse the clarification and rejection forms behind a
  "Query or reject this route" disclosure; run checks and approve stay
  primary.

### 4. Admin model catalogue

- The AI model panel renders each available model as a selectable card
  with a tier chip (Sovereign, Fast, Advanced, or Custom fallback) and a
  one-line description, with an Active badge on the current model.
- The backend records who changed the model and when
  (`changedBy`/`changedAt` on `GET/PUT /api/v1/admin/ai-model`) and the
  panel shows the last change. The existing `ai_model_changed` audit event
  is unchanged.

## Out of scope

- Real LLM calls (provider stays `mock` locally).
- Any change to permission checks, CSRF or session handling.

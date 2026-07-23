# Spec: Intelligence-Grade Intake, Priority Ranking And Team Recommendation

Status: implemented historical specification. Its mandatory human-routing
constraint was superseded by ADR 0036 and the
[customer-search routing contract](customer-search-routing-orchestration.md). Current supported local/test routing
uses the active deterministic JIOC Agent, with JIOC Managers on the loop and in
the loop for exception review or audited intervention.

Extends the [conversational intake](conversational-intake-standard-and-voice.md);
the field list there is
superseded by the standard below. All registry content is synthetic demo data
(MOCK DATA ONLY) with fictional operations and units.

## Purpose

Grow the customer chatbot into an intelligence-tasking front door: a larger
doctrine-flavoured intake, an urgency deep-dive, a natural conversation that
knows how to end, a deterministic internal priority ranking that orders every
queue, and a ranked capability catalogue with a scored team recommendation.

## Intake standard v2

Thirteen entries in elicitation order; ten always required, three
("urgent" entries) required only when the stated priority is critical or high:

1. description, 2. operational_question, 3. area_or_region,
4. time_period (satisfied by `time_period_start`), 5. priority,
6. supported_operation (urgent), 7. urgency_justification (urgent),
8. deadline as latest useful time (urgent), 9. requesting_unit,
10. intelligence_disciplines, 11. required_output_format,
12. customer_success_criteria, 13. title.

The urgency block sits directly after priority so the deep-dive happens the
moment urgency is claimed ("You mentioned this is urgent. Which operation,
exercise or tasking is it in support of?"). `REQUIRED_INTAKE_FIELDS`, the
completeness gate, the then-visible workspace checklist and the assistant's
questions all derive from `INTAKE_STANDARD`. The later
[customer-experience contract](customer-experience-and-analyst-context.md)
removed that checklist from the customer UI while retaining the internal gate.

## Natural conversation

The machinery stays invisible: chat copy never mentions required fields,
checklists or counts; acknowledgement openers rotate deterministically; each
question is self-motivating; the Gemini prompt carries the same instructions.
Extraction stays deterministic and cue-gated
(`services/intake_extractors.py`): the four newer extractors (operation, unit,
disciplines, urgency justification) only fire on explicit cues so a general
message can never silently satisfy them.

## Conversation lifecycle

`TicketRecord.conversation_status` (`open`, `close_offered`, `closed`) is
decided by deterministic rules in `services/conversation_lifecycle.py`, never
by the LLM:

- When the intake becomes complete the assistant asks whether there is
  anything else, and closes on a confirming reply.
- A customer end request ("that's all", "end chat", "submit it") closes the
  chat when the intake is complete; otherwise the assistant explains the query
  cannot be submitted yet and asks the next question.
- A closed conversation rejects further messages (`conversation_closed`) and
  the UI replaces the form with a prompt to review and press Submit. The human
  still presses Submit.

## Internal priority ranking

`domain/prioritisation.py` defines synthetic registries: region tiers (tier 1:
Russia, Kaliningrad, Baltic, Arctic, Eastern Europe, Black Sea), a fictional
operation registry (special forces 1.0 > conventional 0.7 > standing task
0.5 > exercise 0.3) and requesting-unit categories (special forces 1.0 >
intelligence 0.85 > carrier group 0.7 > field army 0.55 > air base 0.4).
`assess_intake` blends priority level 0.35, region 0.25, unit 0.20 and
operation 0.20 into a 0..1 score with tiers P1 (>= 0.8) to P4 and prefixed
reason tags (`priority:region:tier-1:russia`).

The assessment is stored on the ticket whenever the intake changes, recorded
as a `prioritisation-agent` run plus timeline entry at submission, and orders
the RFA/CM routing queues, analyst task list (sorted before truncation), QC
queue and release queues by `(-score, created_at)`. Managers see the tier
badge and reason breakdown; customers see only their stated priority.

## Capability catalogue v2 and team recommendation

`CapabilityTeam` gains disciplines, region coverage and a rank weight; the
enlarged specs live in `services/capability_catalogue_data.py` and include
region-flavoured cells such as the African Imagery Exploitation Cell and the
Eastern Europe Signals Cell. `services/capability_recommendation.py` scores
teams (relevance 0.4, region 0.3, rank 0.2, priority fit 0.1) and returns the
top three `CandidateTeam` entries with reasons. The RFA/CM capability agents
attach `candidate_teams` to their reviews; `suggested_team_id/name` remains
the top candidate, triage fallbacks are preserved, and the manager still
approves every route.

## Non-goals

- Autonomous submission or analyst assignment. The historical prohibition on
  autonomous routing was superseded as described in the status note above.
- Linking analyst users to catalogue teams (flagged follow-up).
- Real operations, units or regionally sensitive weighting; the registries are
  demonstration data.

## Acceptance criteria

- Saying "urgent" mid-conversation expands the applicable checklist from 10 to
  13 entries and triggers the deep-dive questions.
- Both chat-ending paths work as described; closed chats reject messages.
- A critical Russia special-forces request scores 1.0 (P1) and outranks an
  older routine request in every queue.
- Capability reviews carry top-3 candidate teams with reason tags; discipline
  and region signals lift specialist cells over the triage fallback.
- Prompt-injection flags still skip extraction for every intake field and
  never advance or close the conversation.

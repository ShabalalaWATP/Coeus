# Sprint 9 Spec: Analyst Workflow

## Goal

Add the first analyst execution workflow after manager-approved routing. Sprint
9 must let managers assign analysts, let assigned analysts see only their tasks,
record work packages and notes, link permitted Intelligence Store products,
version draft products and submit completed work to QC review.

## In Scope

- Manager assignment from `ANALYST_ASSIGNMENT` to `ANALYST_IN_PROGRESS`.
- Analyst task records on the ticket aggregate.
- Work package checklist creation and completion.
- Analyst note creation with audit trail.
- Linking existing Intelligence Store products after product access checks.
- Draft product versions with metadata, content and optional asset metadata.
- Analyst workbench frontend at `/analyst/workbench` and
  `/analyst/tasks/:taskId`.
- Submission to `QC_REVIEW`.

## Out Of Scope

- QC checklist, approval, rejection and rework. Those start in Sprint 10.
- Automatic product ingestion into the Intelligence Store after QC approval.
- Persistent PostgreSQL task, note and draft tables.
- Real product asset bytes or external storage writes.

## Acceptance Criteria

- Only RFA or collection managers can assign analysts for approved routed work.
- Assigned users must be active Intelligence Analyst seed users.
- Analysts can list and open only tasks assigned to them.
- Analysts can add timestamped notes only while the task is in progress.
- Analysts can link only products visible through existing Store access policy.
- Draft products are versioned and can include asset metadata.
- Submission to QC requires at least one draft and completed work packages.
- Submission transitions the ticket to `QC_REVIEW`.
- Customers cannot access analyst task actions.

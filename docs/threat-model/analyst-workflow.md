# Threat Model: Analyst Workflow

## Scope

Sprint 9 analyst assignment, assigned workbench visibility, work packages,
notes, linked Intelligence Store products, draft product versions and submission
to QC review.

## Assets

- Customer ticket intake and chat context.
- Analyst assignments and work packages.
- Analyst notes and source-product links.
- Draft product metadata, content and asset descriptors.
- QC submission state transitions and audit events.

## Threats And Controls

| Threat | Control in Sprint 9 |
|---|---|
| A customer assigns analysts or mutates analyst work. | Assignment requires RFA or collection assignment permissions. Analyst mutations require analyst permissions and assignment ownership. |
| A descriptive analyst profile is treated as authority. | Assignment validates active status, the generic Analyst role and selected-team membership independently of display name, title, biography or specialisms. |
| An analyst sees another analyst's task. | Workbench listing and task detail require the latest assignment to match the actor's user ID. |
| A linked product bypasses ACG or clearance checks. | Product links call `StoreDetailService.get_visible_product`, reusing Store access policy, and accept only published products. |
| Linking a readable draft grants another task participant a new draft audience. | External Store links reject every draft, including creator-visible and relationship-visible drafts. Ticket-local analyst drafts remain in the dedicated versioned draft workflow, so a link cannot manufacture access authority. |
| Draft product data leaks through published store search. | Sprint 9 draft products remain ticket-local and are not indexed or published. |
| Incomplete work reaches QC. | QC submission requires at least one draft and all work packages marked complete. |
| Notes or drafts are modified after QC submission. | Analyst mutations require `ANALYST_IN_PROGRESS`; submitted tasks enter `QC_REVIEW`. |
| Analyst workflow state changes persist without audit evidence. | Assignment, notes, product links, work-package updates, draft saves and QC submission restore the original ticket if audit recording fails after the ticket update. |

## Residual Risk

- Analyst records are in-memory ticket fields until persistent workflow tables
  are introduced.
- Draft product content is synthetic and local-only. Real file storage, malware
  scanning and release controls are deferred to later ingestion work.
- QC review separation of duties is enforced in the later QC sprint, not Sprint
  9.

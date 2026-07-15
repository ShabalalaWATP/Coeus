# Teams, Profiles and Calendars

## Status

Implemented (2026-07-11), with the generic analyst seed refresh completed on
2026-07-14. See ADR 0022 and ADR 0029.

## Problem

Managers "take ownership" of analysts but the system had no record of who is
on which team, who they are, or who is free on a given date. Assignment
decisions were made blind.

## Domain

`domain/teams.py`, persisted via `repositories/teams.py` in three state-store
namespaces (`teams`, `team_calendar`, `user_profiles`) and seeded from the
seed users (`repositories/teams_seed.py`):

- `OrgTeam { team_id, name, kind: rfa|cm|jioc|qc, manager_user_ids,
member_user_ids, capability_team_id }`. Organisational teams hold people and
  access; the advisory capability catalogue stays separate, with the optional
  `capability_team_id` soft link for the UI.
- `UserProfile { user_id, title, specialisms, bio }` — created for every
  seed user and on first read. Seed profiles carry personal content (title,
  specialisms, bio per user in `repositories/teams_seed_profiles.py`);
  existing profiles are never overwritten during restart seeding.
- `TeamCalendarEntry { entry_id, team_id, user_id, entry_date (ISO date),
end_date (inclusive ISO date, "" = single day), status, note }`. Statuses
  cover the activities members block out: `available`, `on_task`, `leave`,
  `course`, `duty`, `appointment` and `other`. Block entries span
  `entry_date..end_date`; validation requires end >= start, no past starts,
  and the block to end within the 62-day window. Where entries overlap for
  a user on a day, the most recently created entry wins, so a fresh
  single-day override beats an older block.

## Rules

- A team is visible only to its own managers and members; administrators
  (`role:manage`) see all. There is no cross-team user enumeration.
- Roster changes require `team:manage` AND management of that specific team
  (object-level check); targets must be active accounts; changes are audited
  with rollback on audit failure.
- Members write their own calendar entries; the team's managers write
  anyone's on their team. Entries and windows are validated (ISO dates,
  bounded window, bounded note length) and audited.
- Profiles are self-edited (`user:update_self`) with bounded fields, and
  readable by the owner, teammates and administrators only.
- Profile titles, specialisms and biographies are descriptive only. They never
  grant a role, clearance, product access, team membership or assignment
  eligibility.
- Analysts use one generic role and may belong to more than one organisational
  team. Active status, that role and selected-team membership are the
  authoritative assignment boundary.
- Analyst candidates and assignments are restricted to the manager's
  organisational team for the approved RFA or collection route.
- A team is capped at 50 people and directory search returns at most ten
  matches. Server-side pagination is required before raising those bounds.

## Synthetic workforce reconciliation

Local startup reconciles recognised legacy seed identities and untouched seed
profiles to the current fictional workforce. User IDs, credentials, credential
versions, roles, clearance, account status, sessions and team relationships are
preserved. Display names or profiles edited by a user are not overwritten.

## Availability

`TeamAvailabilityService.availability(team, date)` is deterministic: it
combines the calendar statuses covering the date (latest created entry per
member wins, including block entries)
with live analyst assignments on in-flight tickets
(`ANALYST_IN_PROGRESS`, `MANAGER_APPROVAL`, `QC_REVIEW`, `REWORK_REQUIRED`)
and reports `{members, onLeave, onTaskCalendar, otherCommitments,
assignedLive, free}`, where `otherCommitments` counts courses, duty
travel, appointments and other blocks. The
ticket read is a system-level snapshot that only ever surfaces derived counts.

## API

`GET /teams`, `GET /teams/{id}/member-candidates?query=`,
`POST/DELETE /teams/{id}/members[/{userId}]`,
`GET/POST/DELETE /teams/{id}/calendar[/{entryId}]` (window `?from=&to=`),
`GET /teams/{id}/availability?date=`, `GET/PUT /users/me/profile`,
`GET /users/{id}/profile`. All writes are CSRF-validated.

## Frontend

`/teams` ("My Team"): roster with profile titles and specialisms, a manager
add/remove control (directory search with click-to-add suggestions; the
search keeps the directory's minimum-three-character, ten-result
need-to-know posture), a month-grid calendar (Monday-first
weeks, previous/next month navigation, a "Today" highlight, entries as
per-member chips that span block dates, click a day to prefill the form)
with a block-out form (member for managers, activity, from/to dates, note),
and an availability tile for today including other commitments. The dedicated
`/account/profile` route is read-first for every signed-in user and enters an
explicit edit mode before profile fields can be changed. The AssignAnalystPanel shows "X of Y team
members are free today" beside the candidate checkboxes. Non-members see an
informative empty state.

## Tests

`apps/api/tests/test_teams_api.py` covers visibility, roster boundaries,
calendar write rules, the availability calculation against a live assignment,
profile privacy and codec round-trips. Web tests cover the manager and member
views, calendar writes, read-first profile editing, failure paths and the availability
line in the assignment panel.

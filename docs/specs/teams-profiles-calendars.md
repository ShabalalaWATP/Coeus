# Teams, Profiles and Calendars

## Status

Implemented (2026-07-11). See ADR 0022.

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
  seeded team member and on first read.
- `TeamCalendarEntry { entry_id, team_id, user_id, entry_date (ISO date),
  status: available|on_task|leave, note }`.

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

## Availability

`TeamAvailabilityService.availability(team, date)` is deterministic: it
combines the calendar statuses for the date (latest entry per member wins)
with live analyst assignments on in-flight tickets
(`ANALYST_IN_PROGRESS`, `MANAGER_APPROVAL`, `QC_REVIEW`, `REWORK_REQUIRED`)
and reports `{members, onLeave, onTaskCalendar, assignedLive, free}`. The
ticket read is a system-level snapshot that only ever surfaces derived counts.

## API

`GET /teams`, `POST/DELETE /teams/{id}/members[/{userId}]`,
`GET/POST/DELETE /teams/{id}/calendar[/{entryId}]` (window `?from=&to=`),
`GET /teams/{id}/availability?date=`, `GET/PUT /users/me/profile`,
`GET /users/{id}/profile`. All writes are CSRF-validated.

## Frontend

`/teams` ("My Team"): roster with profile titles and specialisms, a manager
add/remove control, the two-week calendar with per-member entries, an
availability tile for today, and the self-service profile editor. The
AssignAnalystPanel shows "X of Y team members are free today" beside the
candidate checkboxes. Non-members see an informative empty state.

## Tests

`apps/api/tests/test_teams_api.py` covers visibility, roster boundaries,
calendar write rules, the availability calculation against a live assignment,
profile privacy and codec round-trips. Web tests cover the manager and member
views, calendar writes, profile saves, failure paths and the availability
line in the assignment panel.

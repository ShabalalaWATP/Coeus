# Threat Model: Teams, Profiles and Calendars

Scope: organisational teams, member profiles, team calendars and the
availability service (`docs/specs/teams-profiles-calendars.md`).

## Assets

- Team rosters (who works where, who manages whom).
- Personal profile data (title, specialisms, bio).
- Calendar entries (leave and tasking patterns are sensitive in aggregate).
- Live workload signals derived from analyst assignments.

## Trust boundaries and controls

| Threat | Control |
| --- | --- |
| Cross-team user enumeration | Teams and profiles are visible only to that team's managers and members (admins excepted); roster candidate search requires both `team:manage` and object-level manager access |
| Assignment display labels spoof team ownership | Assignment writes persist an immutable organisational `team_id`; the server derives the display name and restricts candidates to active members of that selected same-area team. |
| Area manager crosses RFA/CM authority | Assignment team selection and manager review validate the approved route against the team's kind; RFA and CM authority remains area-wide only within its own route kind. |
| Membership tampering | Roster changes require `team:manage` AND management of that specific team (object-level, not just role-level); targets must be active accounts; every change is audited with rollback on audit failure |
| A member forges a teammate's availability | Members may only write their own entries; only the team's managers write for others; entries record `created_by_user_id` |
| Profile impersonation or stored-text abuse | Profiles are self-edit only, with bounded lengths (title 120, specialisms 8x80, bio 1000) validated at the schema boundary; values render as text, never markup |
| A profile title or specialism grants analyst authority | Assignment independently validates active status, the generic Analyst role and membership of the selected organisational team; profiles are descriptive only. |
| A footballer-based seed persona is mistaken for a real personnel record | The dataset and affected screens are labelled synthetic or `MOCK DATA ONLY`; biographies are fictional and make no claim about the real person's work, service or clearance. |
| Display-name collisions change identity | User IDs and usernames remain authoritative for persistence and security decisions; display names are presentation data only. |
| Large rosters enable unbounded enumeration | Teams are capped at 50 people and candidate directory results are bounded to ten; future growth requires paginated server-side queries rather than larger unbounded responses. |
| Calendar as a data sink | Dates must be ISO calendar dates, block ranges must run forwards and end within the bounded window (62 days), activity types are a fixed enum, notes capped at 280 characters |
| Ticket content leaking through availability | The availability service reads a system ticket snapshot but only ever returns derived counts; no ticket fields cross the boundary |
| Cross-team analyst assignment | Candidate discovery and assignment are limited to members of the manager's organisational team for the approved RFA or collection route |
| Audit failure leaves an unrecorded write | Profile, roster and calendar mutations restore their previous repository state when audit persistence fails |
| CSRF on writes | All mutating endpoints require the CSRF header |

## Residual risks

- Aggregate availability counts reveal team workload levels to all team
  members; accepted as the feature's purpose within a team boundary.
- The calendar is app-local by design (no ICS/Outlook sync), so it can drift
  from real-world availability; entries are self-reported.

## July 2026 interface hardening

- Team-directory caches include the team identifier, preventing candidate
  results from crossing team boundaries in the browser cache.
- Calendar dates use local calendar components rather than UTC conversion, and
  duplicate entries render according to the backend latest-entry-wins rule.
- Availability exposes a deduplicated on-task count so overlapping live and
  self-reported work does not overstate team utilisation.
- Membership removal, account deactivation and credential reset require an
  explicit confirmation in the client; server-side authorisation remains the
  controlling security boundary.

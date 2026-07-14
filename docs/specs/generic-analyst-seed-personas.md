# Generic Analyst Seed Personas

## Status

Implemented, 2026-07-14.

## Problem

The local demonstration workforce already uses one `Analyst` role, but three
seed logons encode maritime, cyber and geospatial specialisms in the account
identity. That presentation suggests separate analyst account types and does
not scale cleanly to a workforce with dozens of analysts.

The seed display names and profiles are also generic role labels rather than a
credible, human-readable workforce. This makes team assignment and availability
demonstrations harder to understand.

## Decision

- Keep one generic `Analyst` role and the existing `analyst:work` permission.
- Use neutral analyst logons: `analyst@example.test`,
  `analyst.2@example.test`, `analyst.3@example.test` and
  `analyst.4@example.test`.
- Represent expertise only through the bounded profile fields and
  organisational team membership. Every analyst seed profile uses the title
  `Military Intelligence Analyst`; specialisms and biographies provide the
  individual detail.
- Give all 15 seed accounts distinct display names borrowed from Scottish
  footballers. These are fictional demonstration personas. Their biographies
  do not describe the real people and must not be interpreted as claims about
  their employment, military service or security clearance.
- Keep non-analyst roles intact because the local workflow needs customers,
  routing staff, managers, a store manager, quality control and an
  administrator. Give those accounts realistic synthetic intelligence-workforce
  profiles appropriate to their existing role.
- Keep analyst assignment team-authoritative. An active analyst is eligible
  only when they are a member of the selected RFA or collection team; profile
  specialisms are informative and do not grant authority.
- Preserve the current many-to-many team memberships so the seed demonstrates
  analysts who support one or both operational teams.

## Existing local data

Startup reconciliation must update only untouched legacy seed identities and
profiles. It must:

- preserve user IDs, credential hashes, credential versions, roles, clearance,
  account status, sessions and team membership;
- rename the three specialist analyst usernames without creating duplicates;
- update old seed display names and profiles to the new synthetic personas;
- leave administrator-edited display names and user-edited profiles unchanged;
- remain idempotent across restarts.

No destructive local reset is required for this refresh.

## Acceptance criteria

- The user directory contains 15 accounts with distinct Scottish-footballer
  display names and no specialised analyst role.
- The four analyst accounts all report the same `Analyst` role and
  `Military Intelligence Analyst` profile title.
- The old `analyst.maritime`, `analyst.cyber` and `analyst.geo` logons are not
  present after reconciliation.
- Existing local user IDs and organisational team membership survive the
  reconciliation.
- Seed reconciliation does not overwrite edited display names or profiles.
- Managers can assign the numbered generic analysts only through their current
  team memberships.
- Backend and frontend line and branch coverage remain at least 95 per cent.

## Future scale

The current team roster limit supports dozens of analysts. Before a roster
approaches that size, analyst selection and administration should move from
rendering the full candidate set to server-side search and pagination, with
profile specialisms, availability and current workload included in the
candidate view.

## Verification

- Backend: 68 PostgreSQL tests passed with one expected N-1 compatibility skip;
  919 non-PostgreSQL tests passed. Combined coverage measured 98.13 per cent
  lines and 95.04 per cent branches.
- Frontend: the full Vitest suite passed at 98.51 per cent line coverage and
  95.01 per cent branch coverage. TypeScript, ESLint and the production build
  passed.
- Focused post-reconciliation regression: four seed-persona tests passed after
  adding historical display-label compatibility.
- Live local acceptance: the persistent 15-account directory reconciled without
  a reset, all four generic analysts appeared in the RFA roster, and the updated
  titles, specialisms and biographies rendered on the team page.

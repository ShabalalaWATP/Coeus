# ADR 0029: Generic analyst role and profile specialisation

## Status

Accepted, 2026-07-14.

## Context

Coeus already authorises every analyst through one `Analyst` role, but three
local seed identities encoded maritime, cyber and geospatial disciplines in
their usernames and display names. That made seed personas look like distinct
account types and encouraged future workforce growth through new identities or
roles rather than through the existing team and profile model.

The local demonstration state is persistent. Replacing seed definitions alone
would add duplicate users and would not update existing profiles or team links.

## Decision

- Keep one generic analyst role and permission set.
- Use a primary analyst logon plus numbered analyst logons. Do not encode a
  discipline in a new analyst identity.
- Store descriptive expertise in `UserProfile.specialisms` and `bio` only.
  Profile content never grants permissions, clearance, product access or team
  membership.
- Make organisational team membership, active status and the generic analyst
  role the authoritative analyst-assignment boundary.
- Permit an analyst to belong to more than one team. This expresses shared
  workforce support without adding another role.
- Reconcile recognised legacy seed identities and untouched seed profiles on
  startup while preserving user IDs, credentials, credential versions,
  sessions, roles, clearance, account status and team relationships.
- Use Scottish-footballer display names only for clearly synthetic local
  demonstration personas. Do not make factual claims about the real people.

## Consequences

- Existing local data upgrades without a destructive reset and without
  duplicating the three renamed analyst accounts.
- User-edited display names and profiles remain authoritative and are not
  overwritten by later restarts.
- Team managers can add future generic analysts to the relevant team without a
  code or RBAC change.
- The current roster limit supports dozens of people, but candidate and admin
  views will need server-side search and pagination before substantially larger
  workforces are practical.

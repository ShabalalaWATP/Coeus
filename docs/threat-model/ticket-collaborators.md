# Threat Model: Ticket Collaborators

Scope: the user directory endpoint and collaborator management on tickets.

## Threats and mitigations

- Unauthorised ticket exposure: only the requester (or `ticket:read_all`)
  can tag users; visibility is granted per ticket and revoked by untagging.
- Privilege escalation through tagging: collaborator access is scoped to
  the single ticket. Editors still need their own permissions for
  permission-gated actions (chat requires `chat:use`; timeline additions
  require `ticket:add_information`). Viewers receive read access only, and
  collaborator management itself remains requester-only, so an editor
  cannot widen sharing.
- Product metadata leakage through collaboration: the generic ticket response
  only returns RFI match titles to the requester. Collaborators must use the
  RFI results endpoint, where offers are filtered by their own Store access.
- Account probing through tagging: invalid targets (unknown, disabled,
  self) return one generic `collaborator_invalid` error. The directory
  already lists active users to signed-in users, which is accepted for
  this closed system and keeps tagging deterministic.
- Repudiation: tagging and untagging write timeline entries and audit
  events that record the acting user and target.
- CSRF: all collaborator mutations require the session-bound CSRF header.

## Residual risks

- Any authenticated user can enumerate active usernames via the directory.
  Accepted: the platform is a closed, vetted user base and product metadata
  remains protected by Store ACG, clearance and ownership checks.

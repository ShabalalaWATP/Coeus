# Ticket Collaborators

## Goal

Let a requester tag other Istari users into one of their tickets so those
users can either edit the request alongside them or follow it read-only.

## Behaviour

- `GET /api/v1/users/directory` lists active accounts (id, username, display
  name) excluding the caller, so the UI can offer tag targets. Requires an
  authenticated session.
- `POST /api/v1/tickets/{id}/collaborators` with `{username, access}`
  (`editor` or `viewer`) tags a user. Only the ticket requester (or a
  `ticket:read_all` administrator) may manage collaborators. Unknown,
  disabled or self usernames are rejected with the generic
  `collaborator_invalid` error. Re-tagging a user replaces their access
  level.
- `DELETE /api/v1/tickets/{id}/collaborators/{userId}` untags a user.
- Tagged users see the ticket in `GET /api/v1/tickets` regardless of their
  role. Editors can use ticket chat, edit intake and add timeline
  information, still subject to their own permissions (for example chat
  requires `chat:use`). Viewers can only read.
- Tagging and untagging create timeline entries and audit events.

## Out of scope

- Notifications to tagged users.
- Collaborator management by editors.

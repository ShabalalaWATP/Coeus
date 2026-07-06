# Manager Final Release and Customer Notification

## Goal

Uploading intelligence products and releasing analyst work are manager
responsibilities. QC approval no longer publishes a product directly;
the owning route manager performs the final release, which notifies the
requesting customer.

## Behaviour

- Only RFA and Collection managers (and administrators) hold
  `product:create_existing`, so the store upload route and button are
  manager-only. Team members keep read, search and metadata permissions.
- QC approval ingests and indexes the draft as an unpublished store
  product and moves the ticket to the new `MANAGER_RELEASE` state.
  Dissemination and feedback requests no longer happen at QC time.
- `GET /api/v1/routing/{route}/release-queue` lists tickets awaiting
  release for the manager's route. `POST /api/v1/routing/{ticket_id}/release`
  (CSRF, matching route review permission plus `product:disseminate`)
  publishes the product, disseminates it to the requester, raises the
  feedback request and moves the ticket to `DISSEMINATION_READY`.
- On release the customer receives an in-app notification with a link to
  the product and an email is recorded to the local outbox
  (`email_recorded` audit event). No SMTP relay exists locally; deployed
  environments attach a real delivery provider.
- `GET /api/v1/notifications` returns the caller's notifications and
  unread count; `POST /api/v1/notifications/{id}/read` (CSRF) marks one
  read. The web shell shows an unread badge on the bell and released
  tickets link to their product from the customer dashboard.

## Out of scope

- Real email transport.
- Release delegation or multi-stage release approvals.

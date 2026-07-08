# Threat Model: Manager Final Release

Scope: manager-only product uploads, the `MANAGER_RELEASE` workflow state,
release endpoints and customer notifications.

## Threats and mitigations

- Unauthorised product publication: `product:create_existing`,
  `product:publish` and `product:disseminate` are limited to RFA and
  Collection managers (and administrators). QC-approved products stay in
  draft status, invisible to customers, until the owning RFA or Collection
  manager releases them.
- Cross-route release: the release endpoint validates that the ticket is
  in `MANAGER_RELEASE` and that its approved route matches the caller's
  review permission, so a Collection manager cannot release RFA work and
  vice versa. Repeat releases fail on the state check.
- Partial publication on failed release: release builds the proposed published
  product in memory, validates that the requester would be able to read that
  published product, then saves it. A failed visibility check leaves the product
  in draft, with no dissemination record, ticket transition or release audit.
  If the product is published but the ticket update fails, the previous draft
  product record is restored and requester notification is not sent.
- Separation of duties: QC quality approval and manager release remain
  distinct actions by distinct roles, both audit logged
  (`qc_approved`, `product_released`).
- Notification leakage: notifications are stored per user and only
  returned to their owner; marking read requires the session CSRF token.
  Recorded emails contain only the ticket reference, product reference,
  title and an application link path, never product content.
- Notification flooding: per-user notifications and the email outbox are
  bounded in memory.
- CSRF: release and mark-read mutations require the session-bound CSRF
  header. PUT was added to the CORS allow list for the admin model
  endpoint; allowed origins remain the configured local hosts.

## Residual risks

- Emails are recorded, not transmitted; customers relying only on email
  would not be notified locally. The in-app notification covers local use
  and deployed environments attach a delivery provider.

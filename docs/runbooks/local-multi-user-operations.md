# Local Multi-User Operations Runbook

## Scope

Istari supports multiple synthetic users and roles for development and evaluation
on one trusted local machine. This is not a production identity-management or
organisation-wide hosting guide. The API remains a single writer and the default
Compose ports are loopback-only, so other computers cannot connect without an
explicitly designed and secured network deployment.

## Start the supported local runtime

Follow [Local Development](local-development.md). Keep exactly one API process.
For several people sharing the same evaluation instance, run the browser, API and
PostgreSQL on a controlled host behind TLS rather than exposing development ports
directly. That networked topology is not supplied by this repository.

## Onboard an account

1. The prospective user opens **Request access** on the sign-in page and submits
   a username, display name, password and justification.
2. An administrator opens **Admin > Access requests** and approves or rejects the
   request. Approval creates an active Customer account at clearance level 1.
3. The administrator opens **Users**, finds the account, and assigns only the
   required roles and clearance level.
4. A relevant team manager opens **My Team** and adds the account to the required
   team. Role assignment and team membership are separate controls.
5. An ACG administrator adds the user to the minimum need-to-know groups required
   for their work.
6. The user signs in and updates their profile under **My Team**.

## Manage an account

The **Users** workspace supports search and active/inactive filters. An
administrator can change roles, clearance and account status or issue a temporary
credential. The temporary credential is shown once; transfer it through an
approved channel and require the user to change it immediately.

The signed-in administrator cannot change or deactivate their own account from
this screen. Keep a second tested administrator account before changing another
administrator. Deactivate leavers promptly, remove team and ACG membership, and
review audit events for the change.

## Local data and recovery

- PostgreSQL holds the compatibility state and relational Store projection.
- Uploaded bytes use the configured local object directory.
- The default email provider is an audited local outbox.
- Back up both PostgreSQL and the object directory together while writes are
  stopped. This repository does not provide an automated backup/restore command.
- Test restoration on a separate local instance before relying on a backup.

## Boundaries before real organisational use

Do not treat this local workflow as production-ready until there is an approved
identity provider or persistent production account store, TLS and reverse-proxy
configuration, managed secrets, automated backup/restore, retained audit export,
monitoring, incident response and a reviewed deployment topology. Multiple API
workers or replicas are unsupported.

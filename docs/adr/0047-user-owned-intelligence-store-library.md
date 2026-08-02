# ADR 0047: User-owned Intelligence Store library

## Status

Accepted

## Context

RFI results are useful beyond the immediate accept or reject decision. Browser
bookmarks do not provide an Istari profile, shared-device safety, organisation
or reliable access-control revalidation. A saved copy of product metadata would
also be unsafe because access can change after saving.

## Decision

Store only user-owned references to products plus optional personal folders in
the application state store. The authenticated user ID is the ownership key and
is never accepted from request payloads. Every library read and save resolves
the referenced product through the existing Store visibility service. Hidden
products are omitted and reported as an aggregate unavailable count.

Folder deletion unfiles saved products instead of deleting them. Bounded folder
and saved-product counts prevent this personal convenience feature becoming an
unbounded storage surface. Mutations use CSRF protection and audit events.

The product-detail return action uses validated React Router history state. It
is intentionally ephemeral presentation context and grants no access.

## Consequences

- Personal organisation persists across browsers and local restarts.
- Product access changes take effect immediately in the library.
- Saved items are references, not snapshots, so deleted or newly restricted
  products may appear as unavailable without disclosing their identity.
- A later relational implementation can replace the state-store adapter without
  changing the API or user experience.

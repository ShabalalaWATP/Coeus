# Canonical Team Calendars and Commitments

## Status

Implemented on 4 August 2026 as migration `20260804_0041`. This vertical is
available only wherever the existing organisation-management plane is enabled.
It does not activate relational routing or organisation authority globally.

## Behaviour

- A team event is one canonical record scoped to one active organisational
  unit. It is projected into that unit and authorised ancestor views without
  copying it into member calendars.
- Create, update, occurrence edit, future-series split and cancellation use the
  existing previewed, versioned and actor-bound calendar command boundary.
- Every team mutation requires an effective `calendar:manage` grant covering
  the exact target unit. An unrelated unit is denied at preview and revalidated
  inside the serialisable write transaction.
- Manager-created personal commitments target a subject's effective home unit.
  The subject may acknowledge or dispute them, but cannot silently edit them.
  A dispute requires a short reason. Each manager change resets the response to
  pending and creates a new notification.
- The creator identifier is immutable provenance, not permanent authority. An
  authorised successor may update or cancel a commitment after the original
  manager loses authority.
- Response and event versions make simultaneous manager, subject and recurrence
  exception actions deterministic. A stale action returns a conflict.

## Deduplication

Occurrences are deduplicated only when owner, exact interval, time zone,
activity, availability effect and optional cross-system identity agree. Source
precedence is task, manager, team, personal, external, then legacy. The returned
occurrence retains every contributing source. Removing the winning source
therefore restores the next source rather than deleting the activity.

Conflicting legacy records for the same person and exact interval fail unknown.
They are never added together or silently resolved. Membership-boundary
projection always evaluates the current effective home posting and does not
copy records during a transfer.

## Interface and accessibility

The personal calendar offers month, week and agenda modes. The tabs support
left and right arrow keys, maintain a single keyboard tab stop and collapse to
one column on narrow screens. Pending manager commitments expose labelled
acknowledge and dispute controls. Managers with the explicit grant can create a
team event from the organisation workspace. Technical grant identifiers remain
outside normal user-facing text.

## Verification

- unit tests cover exact multi-source overlap, precedence, restoration and
  corrupt legacy conflicts;
- service tests cover unrelated-team denial and authorised-successor edits;
- real PostgreSQL tests cover migration, team projection, response-version
  races, notifications and exact grant revalidation;
- component tests cover keyboard mode switching, boundary filtering,
  acknowledgement, dispute feedback and team-event payloads.

See [the workforce architecture](../architecture/ORGANISATION_WORKFORCE_AND_CAPACITY.md)
and [the threat model](../threat-model/canonical-team-calendars-and-commitments.md).

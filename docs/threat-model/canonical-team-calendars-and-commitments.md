# Canonical Team Calendar and Commitment Threat Model

## Protected assets

Calendar detail, availability, home-team membership, manager authority,
subject responses, immutable event provenance and notification history are
protected. Calendar notes can reveal sensitive personnel information even when
the availability effect is shareable.

## Threats and controls

| Threat | Control |
| --- | --- |
| Manager writes into an unrelated team | Exact `calendar:manage` lineage is checked during preview and again under the serialisable transaction. The target unit is locked and must be active. |
| Former creator retains control | Authority is evaluated for the current actor. The creator is immutable evidence only. |
| Successor cannot maintain a commitment | A current authorised successor may edit or cancel while provenance still names the original creator. |
| Subject edits a manager commitment | Subjects receive separate versioned acknowledge/dispute commands. Event mutation remains manager-authorised. |
| Concurrent response hides a manager edit | A manager edit increments the event and response versions, resets pending state and notifies the subject. Stale responses fail. |
| Duplicate feeds overstate absence | Exact cross-source identity is collapsed deterministically and contributing sources remain visible. |
| Corrupt legacy overlap is guessed | Conflicting same-interval legacy records return an unavailable/unknown result. |
| Transfer copies or leaks activity | Projection joins canonical records to effective membership at read time. No event is copied on membership change. |
| Private detail leaks through team views | Existing availability/detail grants and event privacy levels still govern projection. |
| CSRF or replay changes a calendar | Mutation and response routes require authenticated CSRF validation; event writes retain actor-bound command idempotency. |

## Residual risk

An incorrect but internally consistent external identity can prevent two
semantically similar events from being combined. This is safer than merging
uncertain personnel commitments. Operators must repair the source mapping or
legacy import rather than override fail-unknown behaviour.

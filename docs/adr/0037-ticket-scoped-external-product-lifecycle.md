# ADR 0037: Ticket-Scoped External Product Lifecycle

## Status

Accepted on 18 July 2026.

## Context

Analysts author final products outside Istari. The existing analyst draft stores
asset metadata but no bytes, while the standalone Store upload can bypass the
ticket's manager and QC gates. QC ingestion currently substitutes placeholder
content, so the approved and delivered artefact is not the analyst's file.

Customers also confirm receipt rather than requirement satisfaction, and
generic feedback has no deterministic workflow effect.

## Decision

1. Add ticket-scoped immutable product submissions for assigned analysts. Keep
   standalone Store ingestion separate and do not grant analysts its permission.
2. Store source files under a workflow namespace. At release, verify the source
   hash and copy the exact bytes into a new immutable Store asset.
3. Preserve original files as authoritative. Treat previews, extraction and QC
   findings as derived artefacts linked to the source hash.
4. Pin manager approval, QC runs, human QC decisions and release to the same
   submission version and hash.
5. Keep automated QC advisory and deterministic. It may block on objective
   integrity or policy failures, but never approves or releases.
6. Require an explicit customer satisfaction decision after release. Route a
   rejection to the owning manager, and a manager disagreement to a JIOC human.
7. Preserve prior Store products on re-analysis. A later release is a new
   revision linked to its predecessor rather than an in-place mutation.

## Consequences

- Real Office and image products can use the governed workflow without forcing
  analysts to re-author them in Istari.
- Source and released bytes remain traceable and hash-verifiable.
- Safe preview processing becomes an explicit operational dependency. Failure
  degrades to extracted text and controlled download, never to unsafe embedding.
- Ticket aggregates gain submission and outcome decision records. Defaults and
  codec identities must remain compatible with older persisted tickets.
- Released products can remain useful in the Store even when one customer asks
  for further analysis.

## Rejected Alternatives

- Giving analysts `product:create_existing`: this bypasses ticket ownership,
  manager review and human QC.
- Embedding Microsoft or Google public document viewers: this would disclose
  protected files to an external service and weaken ACG enforcement.
- Converting and overwriting the source: this destroys evidential integrity.
- Reusing generic feedback as the routing decision: ratings and comments are
  useful analytics but are not a safe workflow command.

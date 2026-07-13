# ADR 0027: Synthetic Releasability And Handling Caveats

## Status

Accepted for Sprint 17, 2026-07-13.

## Context

Coeus is public-repository-safe and prohibits real intelligence content. Store
metadata carries releasability and handling-caveat strings, but `UserAccount`
has no nationality, organisation or handling-eligibility attributes. Treating
free text as an access-control rule would create an unauditable false control.

## Decision

- The supported repository runtime accepts only the synthetic releasability
  marker `MOCK` and handling caveat `MOCK DATA ONLY`, case-normalised on input.
- These markers describe synthetic data and grant no authority. ACG membership,
  clearance, lifecycle and object-aware draft audience remain the access policy.
- Upload, generated-product and QC release boundaries reject missing or
  non-synthetic values before persistence or publication.
- Search and detail apply the same access policy; they do not infer identity
  eligibility from marker text.
- Adding real releasability or caveat vocabularies requires an ADR defining
  controlled values, user eligibility attributes, policy ownership, audit,
  migration and denied fixtures. It cannot be enabled through configuration or
  arbitrary metadata alone.

## Consequences

- Existing synthetic fixtures remain compatible and deterministic.
- Arbitrary labels previously accepted by upload are rejected because they are
  outside the repository's supported synthetic-data contract.
- Deferred scan questions `COEUS-CAN-007` and `COEUS-CAN-008` gain a falsifiable
  current policy without pretending the repository implements a real release
  authority model.

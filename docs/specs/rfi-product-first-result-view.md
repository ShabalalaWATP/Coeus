# RFI product-first result view

## Goal

Make a returned RFI product the primary customer-facing content. Search and
retrieval metadata remains available for assurance and support, but no longer
dominates the normal decision view.

## Content hierarchy

1. Show the product title, summary and mandatory classification marking.
2. Keep the customer's accept or reject decision controls immediately
   available.
3. Put product type, region, asset types, retrieval relevance, match signals
   and grounded evidence in a collapsed `Product details` disclosure.
4. Put workflow state, responsible agent and search metrics in one collapsed
   `Search details` disclosure at the bottom of the panel.
5. Keep degraded-search warnings, loading failures and retry actions visible
   because they materially affect the customer's decision.

## Interaction and accessibility

- Disclosures use native `details` and `summary` elements, are collapsed by
  default, and remain keyboard and screen-reader operable.
- Summary text describes the concealed content without relying on icons alone.
- Focus indicators, contrast and reduced-motion behaviour follow the existing
  application system.
- Read-only viewers retain the same information boundaries and cannot gain new
  actions or data through the presentation change.

## Acceptance criteria

- A returned product's title, summary, classification and decision actions are
  visible without expanding anything.
- Search metrics, retrieval score, match reasons and evidence are not visible
  until their relevant disclosure is opened.
- Expanding each disclosure reveals all information previously available.
- Retry, degraded, loading, error and empty states remain functional.
- Focused component and customer workflow tests pass, with frontend line and
  branch coverage remaining at least 95 per cent.

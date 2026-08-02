# Synthetic provenance and local provider presentation

## Problem

Istari currently repeats `MOCK DATA ONLY` in page headings, product summaries
and administration controls. It also presents the internal provider identifier
`mock` and model identifier `token-hash-v2` as primary user-facing concepts.
The repetition obscures useful content without improving the safety boundary.

## Product intent

- Present the local, no-key AI and retrieval implementations as supported local
  operating modes.
- Keep synthetic provenance clear without placing the same warning in every
  page heading and data field.
- Keep external provider activation deliberate. A configured key must not cause
  unannounced data egress or change the active provider by itself.
- Preserve machine-facing provider, model, releasability and handling values so
  existing persistence, APIs, search releases and authorisation remain stable.

## User experience

1. Every authenticated workspace shows one persistent `Synthetic exercise`
   indicator in the command bar.
2. Individual workspace page headings do not repeat that indicator.
3. Seeded Store titles and descriptive prose read naturally. Product metadata
   retains the synthetic handling caveat, and downloadable reports remain
   clearly marked on every page.
4. Administration labels the internal `mock` provider as `Local assistant` for
   text chat and `Local search` for retrieval.
5. Administration labels `mock` and `token-hash-v2` models as `Local response
   engine` and `Local Search v2`. Technical identifiers remain available in a
   compact disclosure for troubleshooting and release management.
6. External providers appear before the local fallback in selection controls,
   but only a tested and explicitly applied choice becomes active.
7. The Store translates legacy product-type identifiers into operational names
   and keeps internal provenance tags out of primary result and detail chips.

## Safety and compatibility

- Internal provider and model identifiers do not change.
- Fresh local installations continue to work without an API key.
- Hosted provider defaults remain deployment-controlled.
- External text or embedding providers still require the existing key, test,
  activation and egress controls.
- `MOCK` releasability and `MOCK DATA ONLY` handling caveats remain unchanged
  at the product boundary.
- Synthetic PDF content must keep at least one unambiguous provenance marker on
  every page.

## Acceptance criteria

- The authenticated shell exposes exactly one persistent synthetic indicator.
- No production workspace page renders the old `classification-note` warning.
- Store heading copy and seeded descriptive text do not lead with `MOCK DATA
ONLY`.
- Persisted baseline Store records converge on current canonical presentation
  copy without changing their creation dates or assets.
- Both AI administration panels use the local display names and do not expose
  raw local model identifiers as their primary labels.
- Retrieval release and technical identifiers are still inspectable.
- Existing provider activation, indexing, search, access-control and report
  download behaviour is unchanged.
- Frontend accessibility, tests, coverage, lint, type checks and build pass.
- Relevant backend seed, PDF, search and security tests pass after reseeding.

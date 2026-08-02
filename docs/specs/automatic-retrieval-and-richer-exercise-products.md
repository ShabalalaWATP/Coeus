# Automatic retrieval and richer exercise products

## Problem

The Intelligence Store can detect corpus drift but requires an administrator to
start every rebuild. The original catalogue also contains missing object bytes
and formats that are useful to users but not understood by the text extractor.
Generated reports are text-heavy and do not adequately exercise map, imagery,
timeline, translated-extract or multi-source review journeys.

The saved Gemini embeddings credential must also be distinguished from a
credential that Gemini has actually accepted. A stored but rejected key must
not make cloud retrieval appear active.

## Product intent

- Queue one bounded index rebuild when Store products or assets change.
- Recover queued corpus drift after a local restart.
- Preserve shadow-generation promotion and fail-closed provider behaviour.
- Extract bounded text from safe structured formats and index bounded image
  metadata without attempting untrusted OCR.
- Repair missing local exercise assets with deterministic replacement reports.
- Generate operationally useful exercise documents with schematic maps,
  imagery annotations, tables, timelines, daily summaries, translated extracts
  and multi-source assessments.
- Support the stable Gemini text and multimodal embedding model identifiers,
  while requiring a successful provider test and explicit egress confirmation.

## Behaviour

1. A successful Store save, seed upsert, delete or committed QC projection
   signals the automatic rebuild coordinator.
2. Changes are debounced. Only one rebuild runs at a time, and a change arriving
   during a build queues one follow-up pass.
3. On startup, a stale or unindexed corpus is queued even if the process stopped
   before receiving the original change signal.
4. Provider configuration changes also queue a compatible new generation.
5. CSV and GeoJSON are decoded as bounded UTF-8 text. PNG, JPEG and WebP are
   verified and indexed with bounded media metadata. Arbitrary binary remains
   unsupported.
6. Legacy local exercise objects that are missing are replaced by deterministic
   PDF recovery reports and their asset metadata is updated atomically.
7. Gemini failures expose a safe actionable reason such as invalid credential,
   without returning provider response bodies or credential material.
8. The administration page follows queued and running rebuilds automatically.
   It describes the outcome as ready, updating automatically or needing
   attention, without requiring users to understand indexes or generations.
9. Provider identifiers, vector dimensions and generation details remain
   available in a collapsed technical section. Manual rebuild controls are
   presented only as recovery after an automatic rebuild fails.

## Acceptance criteria

- A product mutation results in a ready generation without an administrator
  pressing **Rebuild search index**.
- Multiple rapid mutations coalesce and cannot create concurrent generations.
- All canonical local catalogue assets index without missing or unsupported
  warnings.
- Repaired assets retain their product and asset identities and have matching
  byte length and SHA-256 metadata.
- Generated PDFs contain at least eight rendered pages and include the richer
  operational views without clipping, overlap or unreadable glyphs.
- A rejected Gemini key cannot be activated. A successful candidate test can be
  explicitly applied and automatically rebuilds the corpus in its new space.
- Queued and running rebuilds refresh in the administration page without a
  manual page reload, explain that no action is needed and settle on the ready
  state when complete.
- A healthy or in-progress search library does not offer a manual rebuild
  action. A failed generation offers a plain-language retry action.
- The primary status distinguishes working search from outstanding quality
  assurance. It does not describe a pending evaluation as a search failure.
- Tests cover recovery, mutation coalescing, change-during-build, extraction
  budgets, invalid provider credentials and deterministic document output.

## Out of scope

- OCR of arbitrary uploaded images.
- Fabricating real intelligence or using real operational source material.
- Multi-replica hosted rebuild scheduling. The current worker remains a
  single-process local boundary pending a durable distributed job runner.

# ADR 0031: Deterministic live-demo PDF corpus

## Status

Accepted, 15 July 2026.

## Context

The live Intelligence Store had broad metadata but few real PDF objects. Its
separate generator package was not loaded into the application. Plain-text
placeholder bytes were also being advertised as PDF assets. A larger corpus is
needed to evaluate retrieval and ACG boundaries without introducing real
intelligence content.

## Decision

The local demo seed generates 144 deterministic four-page PDFs from canonical
synthetic source records. ReportLab and pypdf are development dependencies only.
Generated binaries remain in ignored local object storage and are repaired on
each seed run. Product metadata mirrors the PDF themes because synchronous PDF
extraction at application start would add an unsafe, unbounded parsing boundary.

Each product has exactly one specialist ACG. Fifteen specialist ACGs cover
Russia, Iran and China across land, EW, SIGINT, missiles, UAS and cyber themes.
Billy Gilmour receives 56 of the 58 demo ACGs, with two deliberate exclusions
that provide deny-path test cases.

Search scores use absolute lexical and vector evidence. Reciprocal-rank fusion
is retained only as a small ordering signal and is not described as confidence.

## Consequences

- A fresh local demo contains 189 products and 58 ACGs.
- PDF bytes, sizes and hashes are mutually consistent and deterministic.
- Runtime binaries remain generated locally. A reviewed synthetic-only export is
  versioned under `demo-assets/intelligence-store/` for demonstrations.
- Production ingestion still requires sandboxed asynchronous content extraction
  before document-body search can be enabled safely.

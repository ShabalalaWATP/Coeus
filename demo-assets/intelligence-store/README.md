# Synthetic Intelligence Store PDF Library

This directory contains a versioned export of the 144 deterministic PDF
products used by the local Coeus demo. Every document is fictional, visibly
marked `MOCK DATA ONLY` on every page and contains no real units, locations,
sources or operational reporting.

`manifest.json` records the product reference, title, specialist ACG, file size
and SHA-256 digest. The application continues to generate its runtime object
store from canonical source records, so these files are demonstration and
review artefacts rather than an application persistence layer.

Regenerate the export from the repository root with:

```powershell
uv run --project apps/api python scripts/export_demo_pdf_library.py `
  demo-assets/intelligence-store/pdfs
```

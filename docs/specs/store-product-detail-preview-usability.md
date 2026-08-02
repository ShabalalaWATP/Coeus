# Store Product Detail And Preview Usability

## Problem

The Intelligence Store product page gives metadata equal visual weight to the
controlled asset. On products with extensive handling fields and semantic
labels, metadata can occupy most of the first viewport before the operator
reaches the report. PDF previews also use an originless iframe sandbox, which
Microsoft Edge blocks when its built-in PDF viewer tries to load a Blob URL.

## Outcome

- Assets and the selected controlled preview are the primary product workspace.
- Metadata appears after the assets in a compact disclosure that is closed by
  default.
- The collapsed summary retains enough context to identify product type,
  classification and region without opening the disclosure.
- PDF previews work in Microsoft Edge by rendering pages into an inert canvas
  rather than invoking a browser PDF plug-in.
- Existing ACG, clearance, token, expiry and download controls are unchanged.

## Security Boundary

Preview bytes continue to be fetched with the signed token in a request header,
converted to a component-local Blob URL and revoked on replacement, expiry or
unmount. PDF.js reads the Blob in a same-origin worker, stops on parsing errors
and paints one selected page into a canvas. No active PDF content, forms,
annotations, links or scripts are attached to the page DOM. The application
CSP continues to exclude `unsafe-eval`.

## Acceptance Criteria

1. Product assets precede metadata in the document and visual order.
2. Metadata is collapsed by default and can be expanded with the keyboard.
3. The disclosure remains readable on narrow and wide viewports.
4. Raster previews continue to use an image element.
5. PDF previews use the controlled PDF renderer; other non-raster previews keep
   a non-referring iframe with an empty sandbox.
6. Product detail, controlled-preview and browser regression tests pass.
